import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('onboarding', ROOT / 'scripts/onboarding.py')
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)


def profile(mode='publish_recurring'):
    p = json.loads(o.TEMPLATE.read_text())
    p.update(owner_key='example-owner', profile_id='example-profile', mode=mode, series='Example column', timezone='Europe/London')
    p['content'].update(topic='Local walks', audience='Walkers', language='en', format='images', source_kind='public', public_scope='Public facts and owned images')
    p['storage'].update(private_root='/private/example', ledger_ref='private-ledger')
    if mode != 'prepare':
        p['account'].update(id='example-account', display_name='Example')
        p['runtime'].update(kind='mac', id='example-runtime', publisher_id='one-publisher')
    if mode.startswith('publish'):
        p['visibility'] = 'public'
    p['schedule'].update(timezone=p['timezone'], frequency='weekly', publish_times=['09:00'], start_date='2030-01-01', task_id='example-task', notification_ref='current-chat', single_publisher_verified=True)
    p['authorization'].update(granted=True, recorded_at=dt.datetime.now(dt.timezone.utc).isoformat(), instruction_ref='current-user-request')
    p['authorization']['scope'] = {'owner_key':p['owner_key'], 'account_id':p['account']['id'], 'series':p['series'], 'mode':mode, 'visibility':p['visibility'], 'runtime_id':p['runtime']['id'], 'content_scope':{k:copy.deepcopy(p['content'][k]) for k in ['source_kind','source_refs','public_scope','editing','missing_media','privacy']}, 'schedule_scope':{k:copy.deepcopy(p['schedule'][k]) for k in ['timezone','frequency','publish_times','retry_times','start_date']} if mode=='publish_recurring' else None}
    for capability in p['capabilities'].values():
        capability.update(status='VERIFIED', checked_at=dt.datetime.now(dt.timezone.utc).isoformat(), evidence_ref='observed-evidence', runtime_id=p['runtime']['id'], account_id=p['account']['id'])
    return p


class OnboardingTests(unittest.TestCase):
    def test_blank_template_does_not_grant_any_permission(self):
        result = o.check(json.loads(o.TEMPLATE.read_text()), 'new-user')
        self.assertEqual(result['status'], 'NEEDS_SETUP')
        self.assertIn('USER_AUTHORIZATION_REQUIRED', result['blockers'])
        self.assertIn('mode', result['missing_information'])

    def test_copy_only_does_not_request_account_login_or_schedule(self):
        p = profile('prepare')
        for key in ['publisher_control', 'account_session', 'submit_entry', 'scheduler']:
            p['capabilities'][key]['status'] = 'UNKNOWN'
        self.assertEqual(o.check(p, 'example-owner')['status'], 'CONFIG_RECORDED')
        self.assertEqual(o.check(p, 'example-owner')['required_capabilities'], ['source_read','storage_rw'])

    def test_new_user_can_use_non_shanghai_timezone(self):
        self.assertEqual(o.check(profile(), 'example-owner')['status'], 'CONFIG_RECORDED')

    def test_consent_does_not_establish_login(self):
        p = profile()
        p['capabilities']['account_session']['status'] = 'USER_ACTION_REQUIRED'
        self.assertIn('account_session:USER_ACTION_REQUIRED', o.check(p, 'example-owner')['blockers'])

    def test_other_user_account_or_device_cannot_reuse_permissions(self):
        p = profile()
        self.assertIn('OWNER_MISMATCH', o.check(p, 'other-owner')['blockers'])
        p['account']['id'] = 'other-account'
        p['runtime']['id'] = 'other-device'
        result = o.check(p, 'example-owner')
        self.assertIn('AUTHORIZATION_SCOPE_MISMATCH', result['blockers'])
        self.assertIn('account_session:ACCOUNT_MISMATCH', result['blockers'])
        self.assertIn('publisher_control:RUNTIME_MISMATCH', result['blockers'])

    def test_source_expansion_requires_new_scope(self):
        p = profile()
        p['content']['source_refs'] = ['another-private-source']
        self.assertIn('AUTHORIZATION_SCOPE_MISMATCH', o.check(p, 'example-owner')['blockers'])

    def test_deferred_first_use_is_not_verified(self):
        p = profile()
        for key in ['upload_preview','submit_entry','cross_run_reuse']:
            p['capabilities'][key]['status'] = 'PENDING_FIRST_USE'
        result = o.check(p, 'example-owner')
        self.assertEqual(result['status'], 'FIRST_USE_PENDING')
        self.assertEqual(len(result['pending_checks']), 3)
        p['capabilities']['account_session']['status'] = 'PENDING_FIRST_USE'
        self.assertEqual(o.check(p, 'example-owner')['status'], 'NEEDS_SETUP')

    def test_recurring_needs_single_publisher_and_matching_schedule(self):
        p = profile()
        p['schedule'].update(single_publisher_verified=False, timezone='America/New_York')
        result = o.check(p, 'example-owner')
        self.assertIn('SINGLE_PUBLISHER_NOT_VERIFIED', result['blockers'])
        self.assertIn('SCHEDULE_TIMEZONE_MISMATCH', result['blockers'])

    def test_revocation_and_evidence_are_not_silent_success(self):
        p = profile()
        p['authorization']['granted'] = False
        p['capabilities']['account_session']['evidence_ref'] = None
        result = o.check(p, 'example-owner')
        self.assertIn('USER_AUTHORIZATION_REQUIRED', result['blockers'])
        self.assertIn('account_session:EVIDENCE_REQUIRED', result['blockers'])

    def test_optional_archive_failure_is_separate(self):
        p = profile()
        p['archive'].update(enabled=True, private_target='private-storage')
        p['capabilities']['archive_rw']['status'] = 'DENIED'
        self.assertFalse(o.check(p, 'example-owner')['blockers'])
        p['archive']['required_before_publish'] = True
        self.assertIn('archive_rw:DENIED', o.check(p, 'example-owner')['blockers'])

    def test_secrets_rejected_without_echoing_values(self):
        p = profile()
        p['account']['cookie'] = 'example-secret-value'
        result = o.check(p, 'example-owner')
        self.assertIn('CREDENTIAL_FIELD_FORBIDDEN', result['blockers'])
        self.assertNotIn('example-secret-value', json.dumps(result))

    def test_init_is_private_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'profile.json'
            command = [sys.executable, str(o.__file__), 'init', '--config', str(path)]
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            original = path.read_bytes()
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertEqual(path.read_bytes(), original)
            (Path(tmp) / '.git').mkdir()
            command[-1] = str(Path(tmp) / 'another.json')
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertFalse((Path(tmp) / 'another.json').exists())

    def test_schedule_expansion_does_not_reuse_weekly_consent(self):
        p = profile()
        p['schedule']['frequency'] = 'daily'
        self.assertIn('AUTHORIZATION_SCOPE_MISMATCH', o.check(p, 'example-owner')['blockers'])
