from zoneinfo import ZoneInfo
import datetime as datetime_module
DATE = datetime_module.datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import test_brief_workflow as fixture
w = fixture.w
import unittest


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.WorkflowTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.d = self.fixture.directory

    def test_old_receipts_and_scheduled_block_submission(self):
        for status in ['SCHEDULED', '已预约', '已发布', '已公开', '已驳回', '审核中']:
            for key in ['stage', 'submission_result', 'review_status']:
                self.assertEqual(w.decision({key: status}), 'SYNC_ONLY')
        for status in ['准备提交', '提交中', '提交未知', '待核实']:
            self.assertEqual(w.decision({'stage': status}), 'VERIFY_PLATFORM_FIRST')

    def test_manifest_declared_dimensions_must_match(self):
        self.fixture.image['width'] = 2
        with self.assertRaisesRegex(ValueError, 'dimensions differ'):
            w.validate_manifest(self.d, DATE, self.fixture.manifest)

    def test_legacy_published_receipt_cannot_be_downgraded(self):
        w.atomic_json(self.d / '进度.json', {'date':DATE,'stage':'DONE','review_status':'已发布'})
        evidence = self.d / 'receipt.txt'
        evidence.write_text('backend evidence')
        proc = subprocess.run([sys.executable, str(w.__file__), 'result', '--directory', str(self.d), '--date', DATE, '--result', 'REJECTED', '--evidence', evidence.name], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(w.read_json(self.d / '进度.json')['review_status'], '已发布')

    def test_whole_workflow_lock_skips_second_executor(self):
        lockpath = self.d / '.publisher.lock'
        marker = self.d / 'unexpected.txt'
        runner = Path(w.__file__).with_name('run_locked.py')
        command = [sys.executable, str(runner), '--lock', str(lockpath), '--', sys.executable, '-c', 'from pathlib import Path; import sys; Path(sys.argv[1]).write_text("ran")', str(marker)]
        with lockpath.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            proc = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(json.loads(proc.stdout)['action'], 'SKIP_OCCUPIED')
            self.assertFalse(marker.exists())
        subprocess.run(command, check=True)
        self.assertEqual(marker.read_text(), 'ran')

    def test_fresh_checks_cannot_submit_another_day(self):
        for date in ['2000-01-01', '2099-01-01']:
            with self.assertRaisesRegex(ValueError, 'current date'):
                w.begin_submit(self.d, {'date': date, 'stage':'DRAFT'}, {}, date)

    def test_manifest_requires_handoff_metadata(self):
        for key in ['timezone', 'content_version', 'images_expected']:
            manifest = dict(self.fixture.manifest)
            del manifest[key]
            with self.assertRaises(ValueError):
                w.validate_manifest(self.d, DATE, manifest)

    def test_citations_in_headings_and_tables_are_rejected(self):
        for markdown in ['# title private', '| a | b |\n|---|---|\n| private | x |', '# title <Cite ref="private"/>']:
            with self.assertRaisesRegex(ValueError, 'citations'):
                w.render_markdown(markdown, [])
