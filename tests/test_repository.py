from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module

validator = load("validator", ROOT / "scripts" / "validate_skills.py")
installer = load("installer", ROOT / "scripts" / "install_skill.py")

class RepositoryTests(unittest.TestCase):
    def test_repository_validates(self):
        self.assertEqual([], validator.validate_repository())

    def test_registry_matches_metadata(self):
        metas, errors = validator.collect()
        self.assertEqual([], errors)
        reg, errors = validator.validate_registry(metas)
        self.assertEqual([], errors)
        self.assertEqual(set(metas), {x["name"] for x in reg["skills"]})

    def test_each_active_skill_has_contract(self):
        for name in installer.active_skills():
            self.assertEqual([], validator.validate_contract(name))

    def test_install_skill(self):
        name = installer.active_skills()[0]
        with tempfile.TemporaryDirectory() as temp:
            destination = installer.install(name, Path(temp))
            self.assertTrue((destination / "SKILL.md").exists())

    def test_install_refuses_overwrite(self):
        name = installer.active_skills()[0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            installer.install(name, root)
            with self.assertRaises(FileExistsError):
                installer.install(name, root)

if __name__ == "__main__":
    unittest.main()
