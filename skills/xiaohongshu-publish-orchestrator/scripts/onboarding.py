#!/usr/bin/env python3
"""Check private onboarding records. Never logs in, grants access, or publishes."""
import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TEMPLATE = Path(__file__).resolve().parents[1] / 'assets/onboarding-profile.template.json'
MODES = {'prepare', 'draft', 'publish_once', 'publish_recurring'}
STATUSES = {'UNKNOWN', 'VERIFIED', 'DENIED', 'EXPIRED', 'USER_ACTION_REQUIRED', 'PENDING_FIRST_USE'}
SECRET_KEYS = {'password', 'passwd', 'cookie', 'cookies', 'token', 'access_token', 'refresh_token', 'otp', 'verification_code', 'api_key', 'session_data'}


def get(data, dotted):
    for key in dotted.split('.'):
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def check(data, owner_key):
    missing, blocked, pending = [], [], []
    def need(path):
        if get(data, path) in (None, '', []):
            missing.append(path)
    def choice(path, options):
        if get(data, path) not in options:
            missing.append(path)
    def timestamp(value):
        try:
            parsed = dt.datetime.fromisoformat(value)
            return parsed.tzinfo is not None and parsed <= dt.datetime.now(dt.timezone.utc)
        except (TypeError, ValueError):
            return False
    def no_secrets(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.lower() in SECRET_KEYS:
                    blocked.append('CREDENTIAL_FIELD_FORBIDDEN')
                no_secrets(value)
        elif isinstance(obj, list):
            for value in obj:
                no_secrets(value)
    no_secrets(data)
    if data.get('schema_version') != 1:
        blocked.append('UNSUPPORTED_SCHEMA')
    if not owner_key or data.get('owner_key') != owner_key:
        blocked.append('OWNER_MISMATCH')
    for key in ['owner_key', 'profile_id', 'series', 'timezone', 'content.topic', 'content.audience', 'content.language', 'content.public_scope', 'storage.private_root']:
        need(key)
    choice('mode', MODES)
    choice('content.format', {'images', 'longform', 'video'})
    choice('content.source_kind', {'public', 'private', 'mixed'})
    choice('content.editing', {'preserve', 'adapt'})
    choice('content.missing_media', {'pause', 'regenerate'})
    choice('content.privacy', {'redact_personal', 'approved_public_fields'})
    if get(data, 'content.source_kind') in {'private', 'mixed'}:
        need('content.source_refs')
    try:
        ZoneInfo(data.get('timezone') or '')
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        missing.append('timezone')
    if type(get(data, 'content.create_media')) is not bool:
        missing.append('content.create_media')
    mode = data.get('mode')
    platform = mode in {'draft', 'publish_once', 'publish_recurring'}
    publishing = mode in {'publish_once', 'publish_recurring'}
    recurring = mode == 'publish_recurring'
    required = ['source_read', 'storage_rw']
    if get(data, 'content.create_media') is True:
        required.append('media_creation')
    if platform:
        for key in ['account.id', 'runtime.id', 'runtime.publisher_id', 'storage.ledger_ref']:
            need(key)
        choice('runtime.kind', {'mac', 'cloud', 'other_local'})
        required += ['publisher_control', 'account_session', 'upload_preview']
    if publishing:
        need('visibility')
        required.append('submit_entry')
    if recurring:
        for key in ['schedule.frequency', 'schedule.publish_times', 'schedule.start_date', 'schedule.task_id', 'schedule.notification_ref', 'schedule.stop_method']:
            need(key)
        if get(data, 'schedule.timezone') != data.get('timezone'):
            blocked.append('SCHEDULE_TIMEZONE_MISMATCH')
        if get(data, 'schedule.single_publisher_verified') is not True:
            blocked.append('SINGLE_PUBLISHER_NOT_VERIFIED')
        try:
            dt.date.fromisoformat(get(data, 'schedule.start_date'))
        except (TypeError, ValueError):
            missing.append('schedule.start_date')
        for key in ['schedule.publish_times', 'schedule.retry_times']:
            values = get(data, key)
            if not isinstance(values, list):
                missing.append(key)
                continue
            for value in values:
                try:
                    if not isinstance(value, str) or not re.fullmatch(r'\d{2}:\d{2}', value):
                        raise ValueError('Time must be HH:MM')
                    dt.time.fromisoformat(value)
                except (TypeError, ValueError):
                    missing.append(key)
        required += ['scheduler', 'cross_run_reuse']
    if get(data, 'archive.required_before_publish') is True and get(data, 'archive.enabled') is not True:
        blocked.append('REQUIRED_ARCHIVE_DISABLED')
    if get(data, 'archive.enabled') is True:
        need('archive.private_target')
        if get(data, 'archive.required_before_publish') is True:
            required.append('archive_rw')
        elif get(data, 'capabilities.archive_rw.status') != 'VERIFIED':
            pending.append('OPTIONAL_ARCHIVE_UNVERIFIED')
    scope = {'owner_key':data.get('owner_key'), 'account_id':get(data, 'account.id') if platform else None,
             'series':data.get('series'), 'mode':mode, 'visibility':data.get('visibility') if publishing else None,
             'runtime_id':get(data, 'runtime.id') if platform else None,
             'content_scope':{key:get(data, 'content.' + key) for key in ['source_kind', 'source_refs', 'public_scope', 'editing', 'missing_media', 'privacy']},
             'schedule_scope':{key:get(data, 'schedule.' + key) for key in ['timezone','frequency','publish_times','retry_times','start_date']} if recurring else None}
    if get(data, 'authorization.granted') is not True:
        blocked.append('USER_AUTHORIZATION_REQUIRED')
    if get(data, 'authorization.scope') != scope:
        blocked.append('AUTHORIZATION_SCOPE_MISMATCH')
    if not timestamp(get(data, 'authorization.recorded_at')) or not get(data, 'authorization.instruction_ref'):
        blocked.append('AUTHORIZATION_EVIDENCE_REQUIRED')
    for capability in required:
        item = get(data, 'capabilities.' + capability) or {}
        status = item.get('status') if isinstance(item, dict) else None
        if status not in STATUSES:
            blocked.append(capability + ':INVALID_STATUS')
            continue
        if status == 'PENDING_FIRST_USE' and capability in {'upload_preview', 'submit_entry', 'cross_run_reuse'}:
            pending.append(capability + ':PENDING_FIRST_USE')
            continue
        if status != 'VERIFIED':
            blocked.append(capability + ':' + status)
            continue
        if not item.get('evidence_ref') or not timestamp(item.get('checked_at')):
            blocked.append(capability + ':EVIDENCE_REQUIRED')
        if platform and item.get('runtime_id') != get(data, 'runtime.id'):
            blocked.append(capability + ':RUNTIME_MISMATCH')
        if capability in {'account_session', 'upload_preview', 'submit_entry'} and item.get('account_id') != get(data, 'account.id'):
            blocked.append(capability + ':ACCOUNT_MISMATCH')
    result = 'NEEDS_SETUP' if missing or blocked else ('FIRST_USE_PENDING' if any(x.endswith(':PENDING_FIRST_USE') for x in pending) else 'CONFIG_RECORDED')
    return {'status':result, 'missing_information':sorted(set(missing)), 'required_capabilities':required,
            'blockers':sorted(set(blocked)), 'pending_checks':pending,
            'notice':'Configuration evidence only. Recheck live identity, authorization, dedupe and preview before each write; this is not permission to submit.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'check'])
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--owner-key', help='Current private user/workspace identity; required for check')
    args = parser.parse_args()
    if args.command == 'init':
        path = args.config.resolve()
        if any((parent / '.git').exists() for parent in path.parents):
            raise ValueError('Use private storage outside any Git checkout')
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(TEMPLATE.read_text(encoding='utf-8'))
        print(json.dumps({'status':'UNCONFIGURED', 'authorization_granted':False}))
        return 0
    if not args.owner_key:
        parser.error('--owner-key is required for check')
    data = json.loads(args.config.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Profile must be a JSON object')
    result = check(data, args.owner_key)
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result['status'] == 'NEEDS_SETUP' else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TypeError) as exc:
        # Never echo input values, paths or credential fragments.
        print(json.dumps({'status':'INVALID_PROFILE', 'error_type':type(exc).__name__}))
        raise SystemExit(2)
