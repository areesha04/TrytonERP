#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import base64
import json
import sys
from argparse import ArgumentParser
from pathlib import Path
from urllib.parse import unquote, urlparse, urlunparse

import requests
from blessings import Terminal

try:
    import argcomplete
except ImportError:
    argcomplete = None


t = Terminal()


def _json_object_hook(dct):
    if dct.get('__class__') == 'bytes':
        return base64.decodebytes(dct['base64'].encode('utf-8'))
    return dct


def _normalize_url(url):
    return url.rstrip('/')


def _parse_env(value):
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError('Environment must include scheme and host')
    if not parsed.username or not parsed.password:
        raise ValueError('Environment must include user and password')
    path = parsed.path or ''
    if not path or path == '/':
        raise ValueError('Environment must include database in path')
    database = path.rstrip('/').split('/')[-1]
    clean_netloc = parsed.hostname
    if parsed.port:
        clean_netloc = '%s:%s' % (parsed.hostname, parsed.port)
    clean_url = urlunparse((
        parsed.scheme,
        clean_netloc,
        parsed.path.rstrip('/'),
        '', '', '',
        ))
    return {
        'url': clean_url,
        'database': database,
        'username': unquote(parsed.username),
        'password': unquote(parsed.password),
    }


def _call(url, username, password, data, session):
    headers = {
        'Content-type': 'application/json',
        'Authorization': 'Basic ' + base64.b64encode(
            f"{username}:{password}".encode()).decode(),
        }
    try:
        response = session.post(url, data=json.dumps(data), headers=headers)
    except requests.RequestException as exc:
        raise RuntimeError('Request error for %s: %s' % (url, exc))
    if response.status_code != 200:
        raise RuntimeError(
            'Request error for %s: %s' % (url, response.reason))
    try:
        payload = json.loads(response.text, object_hook=_json_object_hook)
    except ValueError:
        raise RuntimeError('Invalid JSON response from %s' % url)
    if isinstance(payload, dict) and 'result' in payload:
        payload = payload['result']
    if isinstance(payload, dict) and payload.get('error'):
        error = payload['error']
        if isinstance(error, dict):
            message = error.get('message') or error.get('data') or str(error)
        else:
            message = str(error)
        raise RuntimeError(message)
    return payload


def _get_context(url, username, password, output_format, session):
    data = {'method': 'model.res.user.get_preferences', 'params': [True, {}]}
    context = _call(url, username, password, data, session)
    context['output_format'] = output_format
    return context


def _get_stack(url, username, password, context, stacks, session):
    data = {'method': 'model.ir.action.report.stack',
        'params': [stacks, context]}
    return _call(url, username, password, data, session)


def _is_expected_report(value, output_format):
    report_output_format = value.get('output_format')
    if output_format == 'html':
        return report_output_format in (None, 'html')
    return report_output_format == 'pdf'


def _safe_name(value):
    chars = []
    for char in value:
        if char.isalnum() or char in ('-', '_', '.'):
            chars.append(char)
        else:
            chars.append('_')
    return ''.join(chars).strip('_.') or 'report'


def _select_reports(result_source, result_target, output_format):
    selected = {}
    total = len(result_target)
    for idx, (key, value_target) in enumerate(result_target.items(), start=1):
        if key.startswith('marketing'):
            continue

        print(t.bold('%s/%s reports: %s' % (idx, total, key)))
        value_source = result_source.get(key)
        if not value_source:
            continue
        if not (_is_expected_report(value_target, output_format)
                and _is_expected_report(value_source, output_format)):
            continue
        selected[key] = {
            'source': value_source,
            'target': value_target,
            }
    return selected


def _file_name(report, extension):
    report_name = _safe_name(report.get('report_name') or 'report')
    company = report.get('company', -1)
    ids = '-'.join(str(i) for i in report.get('ids', [])) or 'no-ids'
    return f'{report_name}__company-{company}__ids-{ids}.{extension}'


def _write_log(path, entries):
    with open(path, 'w', encoding='utf-8') as output:
        json.dump(entries, output, indent=2, ensure_ascii=False, sort_keys=True)
        output.write('\n')


def _export_reports(base_dir, database, reports, output_format):
    output_dir = Path(base_dir) / _safe_name(database)
    output_dir.mkdir(parents=True, exist_ok=True)

    extension = 'pdf' if output_format == 'pdf' else 'html'
    exported = 0
    log_entries = []
    for key, report in reports.items():
        entry = {
            'key': key,
            'report_id': report.get('report_id'),
            'report_name': report.get('report_name'),
            'model': report.get('model'),
            'ids': report.get('ids', []),
            'company': report.get('company'),
            'output_format': report.get('output_format'),
            'error': report.get('error'),
            }
        content = report.get('content')
        if report.get('error'):
            log_entries.append(entry)
            print(t.red('Report error %s: %s' % (key, report.get('error'))))
            continue
        if output_format == 'pdf':
            if not isinstance(content, (bytes, bytearray)):
                entry['error'] = 'content is not PDF bytes'
                log_entries.append(entry)
                print(t.red('Skipping %s: content is not PDF bytes.' % key))
                continue
            data = bytes(content)
        else:
            if not isinstance(content, str):
                entry['error'] = 'content is not HTML text'
                log_entries.append(entry)
                print(t.red('Skipping %s: content is not HTML text.' % key))
                continue
            data = content

        filename = _file_name(report, extension)
        output_path = output_dir / filename
        if output_format == 'pdf':
            output_path.write_bytes(data)
        else:
            output_path.write_text(data, encoding='utf-8')
        entry['filename'] = filename
        log_entries.append(entry)
        exported += 1

    log_path = output_dir / 'export_log.json'
    _write_log(log_path, log_entries)
    return output_dir, log_path, exported, len(log_entries) - exported


def main(source, target, output_dir, output_format):
    source_url = _normalize_url(source['url'])
    target_url = _normalize_url(target['url'])

    session_source = requests.Session()
    session_target = requests.Session()

    print(t.bold('Connecting to target: %s@%s' % (
        target['username'], target_url)))
    context_target = _get_context(
        target_url, target['username'], target['password'], output_format,
        session_target)
    result_target = _get_stack(
        target_url, target['username'], target['password'], context_target, {},
        session_target)

    stacks = {key: {
        'ids': value.get('ids', []),
        'company': value.get('company', -1),
        } for key, value in result_target.items()}

    print(t.bold('Connecting to source: %s@%s' % (
        source['username'], source_url)))
    context_source = _get_context(
        source_url, source['username'], source['password'], output_format,
        session_source)
    result_source = _get_stack(
        source_url, source['username'], source['password'], context_source,
        stacks,
        session_source)

    reports = _select_reports(result_source, result_target, output_format)
    report_source = {
        key: values['source'] for key, values in reports.items()}
    report_target = {
        key: values['target'] for key, values in reports.items()}

    source_dir, source_log, source_count, source_skipped = _export_reports(
        output_dir, source['database'], report_source, output_format)
    target_dir, target_log, target_count, target_skipped = _export_reports(
        output_dir, target['database'], report_target, output_format)

    print(t.green(
        'Saved %s source %s files to %s and %s target %s files to %s.' % (
            source_count, output_format.upper(), source_dir,
            target_count, output_format.upper(), target_dir)))
    print(t.green('Logs: %s and %s.' % (source_log, target_log)))
    if source_skipped or target_skipped:
        print(t.red('Skipped reports: source=%s target=%s.' % (
            source_skipped, target_skipped)))


def run():
    parser = ArgumentParser(
        description='Export HTML or PDF report stacks from two Tryton environments.')
    parser.add_argument('source',
        help='Origin env (e.g. https://user:pass@host/dbname)')
    parser.add_argument('target',
        help='Destination env (e.g. https://user:pass@host/dbname)')
    parser.add_argument('--output-format', default='html',
        choices=['html', 'pdf'],
        help='Format to export')
    parser.add_argument('--output-dir', default='report_exports',
        help='Base directory to save exported files grouped by database')
    if argcomplete:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()
    try:
        source = _parse_env(args.source)
        target = _parse_env(args.target)
        main(source, target, args.output_dir, args.output_format)
    except Exception as exc:
        print(t.red(str(exc)), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    run()
