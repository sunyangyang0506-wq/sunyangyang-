import concurrent.futures
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zlib

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "brief_workflow.py"
spec = importlib.util.spec_from_file_location("workflow", SCRIPT)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def png():
    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0")) + chunk(b"IEND", b"")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name) / "2030-01-02"
        self.directory.mkdir()
        self.addCleanup(self.tmp.cleanup)
        (self.directory / "01.png").write_bytes(png())
        self.image = {"number": 1, "file": "01.png", "caption": "A caption", "sha256": hashlib.sha256(png()).hexdigest()}
        self.manifest = {"date": "2030-01-02", "images": [self.image]}

    def test_manifest_rejects_corruption_wrong_date_and_missing_original(self):
        self.assertEqual(w.validate_manifest(self.directory, "2030-01-02", self.manifest)[0]["width"], 1)
        with self.assertRaises(ValueError):
            w.validate_manifest(self.directory, "2030-01-03", self.manifest)
        (self.directory / "01.png").write_bytes(png()[:-12])
        with self.assertRaises(ValueError):
            w.validate_manifest(self.directory, "2030-01-02", self.manifest)
        (self.directory / "01.png").unlink()
        with self.assertRaises(ValueError):
            w.validate_manifest(self.directory, "2030-01-02", self.manifest)

    def test_png_integrity_catches_truncated_stream_even_with_new_manifest_hash(self):
        (self.directory / "01.png").write_bytes(png()[:-12])
        with self.assertRaises(ValueError):
            w.png_dimensions(self.directory / "01.png")

    def test_upload_copy_preserves_dimensions_original_and_transparency_on_white(self):
        from PIL import Image, PngImagePlugin
        source = self.directory / "rgba.png"
        info = PngImagePlugin.PngInfo()
        info.add_text("private_note", "must not appear in upload metadata")
        Image.new("RGBA", (18, 12), (255, 0, 0, 0)).save(source, pnginfo=info)
        original = source.read_bytes()
        destination = self.directory / "copy.jpg"
        with mock.patch.object(w.subprocess, "run", side_effect=AssertionError("No Mac command allowed")):
            self.assertEqual(w.upload_jpeg(source, destination), "Pillow")
        self.assertEqual(source.read_bytes(), original)
        with Image.open(destination) as upload:
            upload.load()
            self.assertEqual((upload.format, upload.size, upload.mode), ("JPEG", (18, 12), "RGB"))
            self.assertEqual(upload.getpixel((9, 6)), (255, 255, 255))
            self.assertNotIn("private_note", upload.info)

    def test_prepare_without_mac_commands_emits_decodable_upload_and_preserves_original(self):
        from PIL import Image
        original = (self.directory / "01.png").read_bytes()
        manifest = self.directory / "manifest.json"
        manifest.write_text(json.dumps(self.manifest))
        markdown = self.directory / "brief.md"
        markdown.write_text("# 2030-01-02 brief\n## News\nFull body\n![card](01.png)\nA caption")
        argv = [str(SCRIPT), "prepare", "--directory", str(self.directory), "--date", "2030-01-02",
                "--manifest", str(manifest), "--markdown", str(markdown)]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(w.subprocess, "run", side_effect=AssertionError("No Mac command allowed")):
            w.main()
        self.assertEqual((self.directory / "01.png").read_bytes(), original)
        state = w.read_json(self.directory / "进度.json")
        self.assertEqual(state["stage"], "MEDIA_VERIFIED")
        self.assertEqual(state["upload_derivatives"][0]["conversion_backend"], "Pillow")
        with Image.open(self.directory / "01-上传兼容.jpg") as upload:
            upload.load()
            self.assertEqual((upload.format, upload.size), ("JPEG", (1, 1)))
        self.assertIn("<h2>News</h2>\n<p>Full body</p>", (self.directory / "发布正文.html").read_text())

    def test_missing_converter_does_not_change_original_or_write_upload(self):
        original = (self.directory / "01.png").read_bytes()
        with mock.patch.dict(sys.modules, {"PIL": None}), mock.patch.object(w.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "needs Pillow"):
                w.upload_jpeg(self.directory / "01.png", self.directory / "copy.jpg")
        self.assertEqual((self.directory / "01.png").read_bytes(), original)
        self.assertFalse((self.directory / "copy.jpg").exists())

    def test_heading_does_not_absorb_body_and_table_keeps_all_cells(self):
        md = "# 2030-01-02 brief\n## News\nFull body\n\n![card](01.png)\nA caption\n\n| City | Value |\n| --- | --- |\n| One | 17 |\n| Two | 25 |\n[Source](https://example.org)"
        rendered = w.render_markdown(md, [self.image])
        self.assertIn("<h2>News</h2>\n<p>Full body</p>", rendered)
        self.assertEqual(rendered.count("A caption"), 1)
        for cell in ["City：One", "Value：17", "City：Two", "Value：25", "https://example.org"]:
            self.assertIn(cell, rendered)
        with self.assertRaises(ValueError):
            w.render_markdown(md.replace("01.png", "02.png"), [self.image])

    def checks(self):
        (self.directory / "preview.jpg").write_bytes(b"test evidence fixture")
        return dict({key: True for key in w.REQUIRED}, date="2030-01-02", checked_at=w.now(), evidence_file="preview.jpg", images_expected=1, images_loaded_count=1)

    def test_stale_partial_or_count_mismatched_checks_cannot_submit(self):
        state = {"date": "2030-01-02", "stage": "DRAFT", "images_expected": 1}
        checks = self.checks()
        checks["privacy_pass"] = "true"
        with self.assertRaises(ValueError):
            w.begin_submit(self.directory, state, checks, "2030-01-02")
        checks = self.checks()
        checks["checked_at"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()
        with self.assertRaises(ValueError):
            w.begin_submit(self.directory, state, checks, "2030-01-02")
        checks = self.checks()
        checks.update(images_expected=2, images_loaded_count=2)
        with self.assertRaises(ValueError):
            w.begin_submit(self.directory, state, checks, "2030-01-02")

    def test_confirmed_or_unknown_receipts_never_create_a_second_submission(self):
        for stage in ["UNDER_REVIEW", "PUBLISHED", "REJECTED", "SUBMITTING", "UNKNOWN"]:
            state = {"stage": stage}
            self.assertNotEqual(w.begin_submit(self.directory, state, {}, "2030-01-02")["action"], "SUBMIT_ONCE")

    def test_concurrent_runs_grant_only_one_submit_intent(self):
        w.atomic_json(self.directory / "进度.json", {"date": "2030-01-02", "stage": "DRAFT", "images_expected": 1})
        checks = self.directory / "checks.json"
        checks.write_text(json.dumps(self.checks()))
        command = [sys.executable, str(SCRIPT), "begin-submit", "--directory", str(self.directory), "--date", "2030-01-02", "--checks", str(checks)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: subprocess.run(command, capture_output=True, text=True, check=True), range(2)))
        actions = [json.loads(r.stdout)["action"] for r in results]
        self.assertCountEqual(actions, ["SUBMIT_ONCE", "VERIFY_PLATFORM_FIRST"])

    def test_unknown_result_requires_explicit_evidence_before_retry(self):
        state = {"date": "2030-01-02", "stage": "UNKNOWN"}
        w.atomic_json(self.directory / "进度.json", state)
        checks_path = self.directory / "checks.json"
        checks = self.checks()
        checks_path.write_text(json.dumps(checks))
        command = [sys.executable, str(SCRIPT), "resolve-unsubmitted", "--directory", str(self.directory), "--date", "2030-01-02", "--checks", str(checks_path)]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
        self.assertEqual(w.read_json(self.directory / "进度.json")["stage"], "UNKNOWN")
        checks.update(submission_explicitly_absent=True, same_draft_verified=True)
        checks_path.write_text(json.dumps(checks))
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(w.read_json(self.directory / "进度.json")["stage"], "DRAFT")


if __name__ == "__main__":
    unittest.main()
