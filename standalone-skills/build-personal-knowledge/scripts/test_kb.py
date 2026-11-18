import copy
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from kb import allowed, build_files, clock, events, export_snapshot, ingest, open_db, read, review
from kb_capture import capture_chat, capture_codex
from kb_sync import blob_id, publish

ASSETS = Path(__file__).resolve().parents[1]/"assets"

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = open_db(":memory:")
        self.addCleanup(self.db.close)
        self.p = read(ASSETS/"policy.example.json")
        self.b = read(ASSETS/"replay.json")
        self.p.update(repository="sample/notes",repository_id="7")

    def add(self):
        return ingest(self.db,self.p,self.b)

    def test_triple_replay(self):
        self.assertEqual([self.add()["inserted"] for _ in range(3)],[5,0,0])
        rows=events(self.db,self.p)
        self.assertEqual([r["state"] for r in rows],["expressed","suggested","expressed","observed","candidate"])

    def test_history(self):
        self.add()
        self.b["items"][0]["statement"]="需要离线修改。"
        self.assertEqual(self.add()["inserted"],1)
        self.assertEqual(len(events(self.db,self.p,as_of=5)),5)

    def test_misattribution_rolls_back(self):
        self.b["items"][1]["kind"]="decision"
        with self.assertRaises(ValueError):
            self.add()
        self.assertFalse(events(self.db,self.p))

    def test_source_scope(self):
        self.b["items"][-1]["topic"]="forbidden"
        with self.assertRaises(ValueError):
            self.add()
        self.assertFalse(events(self.db,self.p))

    def test_revocation(self):
        self.add()
        self.p["sources"]["training"]["read"]=False
        self.assertFalse(events(self.db,self.p))
        self.assertFalse(allowed(self.p,"training","sync"))

    def test_sensitive_and_secret(self):
        self.b["items"][0]["sensitivity"]="enterprise"
        self.b["items"][1]["statement"]="password: example-only-1234"
        self.assertEqual(self.add()["filtered"],2)
        self.assertNotIn("example-only",str(build_files(events(self.db,self.p))))

    def test_noisy_input(self):
        self.b["items"][0]["statement"]="嗯嗯"
        self.assertEqual(self.add()["filtered"],1)

    def test_relations_and_export(self):
        self.add()
        parent=events(self.db,self.p)[0]["id"]
        self.b["items"]=[dict(self.b["items"][1],kind="method",item="method-1",parent=parent,relation="reuses")]
        self.add()
        with tempfile.TemporaryDirectory() as temp:
            out=export_snapshot(self.db,self.p,Path(temp))
            self.assertEqual(out,export_snapshot(self.db,self.p,Path(temp)))
            snap=read(Path(out["directory"])/"indexes/snapshot.json")
            self.assertEqual(len(snap["knowledge"]),1)
            self.assertEqual(snap["relations"][0]["from"],parent)

    def test_review_threshold(self):
        self.add()
        t=clock("2026-04-01T00:00:00+00:00")
        meta=dict(source="training",last_activity=t.isoformat(),checked_through=(t+timedelta(hours=48)).isoformat(),coverage="complete")
        get=lambda m,n: review(self.db,self.p,m,n,48)["review"]
        self.assertEqual(get(meta,t+timedelta(hours=47,minutes=59)),"active")
        self.assertEqual(get(meta,t+timedelta(hours=48)),"ready")
        self.assertEqual(get(meta,t+timedelta(hours=48)),"unchanged")
        self.assertEqual(get(dict(meta,coverage="partial"),t),"coverage_unknown")
        self.assertEqual(get(meta,t+timedelta(hours=49)),"coverage_unknown")

    def test_chat_selected_branch_and_local_only(self):
        node=lambda role,text,parent:dict(parent=parent,message=dict(author=dict(role=role),content=dict(content_type="text",parts=[text])))
        branch={"id":"c","current_node":"b","mapping":{"a":node("user","A",None),"b":node("assistant","B","a"),"x":node("user","X","a")}}
        rows=capture_chat([branch],"c","booking")
        self.assertEqual([r["statement"] for r in rows],["A","B"])
        ingest(self.db,self.p,{"source":"training","items":rows})
        self.assertFalse(events(self.db,self.p,"sync"))

    def test_codex_whitelist(self):
        data=[{"type":"thread.started","thread_id":"r"},{"type":"turn.started"},
              {"type":"item.completed","item":{"type":"reasoning","text":"omit"}},
              {"type":"item.completed","item":{"id":"i","type":"command_execution","command":"omit","aggregated_output":"omit","exit_code":0}},
              {"type":"turn.completed"}]
        result=capture_codex(map(json.dumps,data),"r","booking")
        self.assertEqual(len(result),2)
        self.assertNotIn("omit",str(result))
        self.assertFalse(any(r["kind"]=="verification" for r in result))

    def test_host_distillation(self):
        from kb_distill import prepare, apply
        self.b["items"]=[dict(self.b["items"][0],local_only=True)]
        self.add()
        with self.assertRaises(ValueError):
            prepare(self.db,self.p,"training")
        self.p["sources"]["training"].update(model=True,model_batch_limit=5)
        batch=prepare(self.db,self.p,"training")
        eid=batch["records"][0]["id"]
        decision=dict(id=eid,kind="idea",title="检索需求",statement="希望断网可查。",evidence="未出现")
        answer=dict(version=batch["version"],source="training",decisions=[decision])
        with self.assertRaises(ValueError):
            apply(self.db,self.p,"training",answer)
        decision["evidence"]="离线查找"
        self.assertEqual(apply(self.db,self.p,"training",answer)["inserted"],1)
        self.assertFalse(prepare(self.db,self.p,"training")["records"])
        exported=events(self.db,self.p,"sync")
        self.assertEqual(len(exported),1)
        self.assertEqual(exported[0]["derived_from"],eid)
        self.assertEqual(exported[0]["state"],"candidate")

    def test_private_target_and_readback(self):
        files={"test.json":"{}"}
        state={"head":"old","tree":[],"writes":0,"public":True}
        def api(method,path,data=None):
            if path=="repos/sample/notes":
                return dict(private=not state["public"],id=7,full_name="sample/notes",permissions=dict(push=True),default_branch="main")
            if "/git/ref/" in path:
                return dict(object=dict(sha=state["head"]))
            if method=="GET" and "/git/commits/" in path:
                return dict(tree=dict(sha=path.split("/")[-1]))
            if method=="GET" and "/git/trees/" in path:
                return dict(tree=state["tree"] if state["head"]=="new" else [])
            if path.endswith("/git/trees"):
                state["tree"]=[dict(path=e["path"],sha=blob_id(e["content"]),type="blob") for e in data["tree"]]
                return {"sha":"newtree"}
            if path.endswith("/git/commits"):
                state["writes"]+=1
                return {"sha":"new"}
            if method=="PATCH":
                state["head"]="new"
                raise OSError("simulated lost receipt")
            raise AssertionError((method,path))
        with self.assertRaises(ValueError):
            publish(self.db,self.p,files,api=api)
        self.assertEqual(state["writes"],0)
        state["public"]=False
        for _ in range(3):
            self.assertEqual(publish(self.db,self.p,files,api=api)["status"],"verified")
        self.assertEqual(state["writes"],1)

if __name__=="__main__":
    unittest.main()
