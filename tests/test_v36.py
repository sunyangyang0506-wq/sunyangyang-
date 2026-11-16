from __future__ import annotations
import importlib.util, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec)
    assert spec and spec.loader; sys.modules[name]=mod; spec.loader.exec_module(mod); return mod
golden=load("golden_v36",ROOT/"scripts"/"eval_golden.py")
installer=load("installer_v36",ROOT/"scripts"/"install_skill.py")

class V36Tests(unittest.TestCase):
    def test_golden_dataset(self):
        self.assertEqual([],golden.validate_dataset())
        self.assertGreaterEqual(len(golden.load_cases()["cases"]),15)
    def test_assertions(self):
        t="DUPLICATE_BLOCKED 重复内容已阻止"
        self.assertTrue(golden.check(t,{"type":"contains_any","values":["重复","阻止"]}))
        self.assertTrue(golden.check(t,{"type":"not_contains","values":["发布成功"]}))
    def test_workspace_install_contract_and_shared(self):
        e=installer.by_name()["douyin-persona-audit"]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); dest,state=installer.install_entry(e,root)
            self.assertEqual("installed",state)
            self.assertTrue((dest/"SKILL.md").exists())
            self.assertTrue((root/e["contract"]).exists())
            for rel in e["shared_dependencies"]: self.assertTrue((root/rel).exists())
    def test_upgrade_same_version_noop(self):
        e=installer.active_entries()[0]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); installer.install_entry(e,root)
            _,state=installer.install_entry(e,root,upgrade=True)
            self.assertEqual("up-to-date",state)

if __name__=="__main__": unittest.main()
