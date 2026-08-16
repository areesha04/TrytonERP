#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import base64
import difflib
import json
import sys
from argparse import ArgumentParser
from urllib.parse import unquote, urlparse, urlunparse

import requests
from blessings import Terminal

try:
    import argcomplete
except ImportError:
    argcomplete = None


t = Terminal()


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
        payload = response.json()
    except ValueError:
        raise RuntimeError('Invalid JSON response from %s' % url)
    if isinstance(payload, dict) and payload.get('error'):
        error = payload['error']
        if isinstance(error, dict):
            message = error.get('message') or error.get('data') or str(error)
        else:
            message = str(error)
        raise RuntimeError(message)
    return payload


def _get_context(url, username, password, session):
    data = {'method': 'model.res.user.get_preferences', 'params': [True, {}]}
    return _call(url, username, password, data, session)


def _get_stack(url, username, password, context, stacks, session):
    data = {'method': 'model.ir.action.report.stack',
        'params': [stacks, context]}
    return _call(url, username, password, data, session)


def _colorize_diff(text):
    lines = []
    for line in text.splitlines():
        if line.startswith('+++') or line.startswith('---'):
            lines.append(t.bold(line))
        elif line.startswith('@@'):
            lines.append(t.bold(line))
        elif line.startswith('+'):
            lines.append(t.green(line))
        elif line.startswith('-'):
            lines.append(t.red(line))
        else:
            lines.append(line)
    return '\n'.join(lines)


def _format_report_info(value, error_detail):
    return '\n'.join([
        'report_id: %s' % value.get('report_id'),
        'report_name: %s' % value.get('report_name'),
        'model: %s' % value.get('model'),
        'ids: %s' % value.get('ids'),
        'company: %s' % value.get('company'),
        'error: %s' % error_detail,
        ])


def _diff_reports(source_name, target_name, result_source, result_target):
    differences = 0
    pending = []
    total = len(result_target)
    for idx, (key, value_target) in enumerate(result_target.items(), start=1):
        print(t.bold('%s/%s reports: %s' % (idx, total, key)))
        value_source = result_source.get(key)
        if not value_source:
            continue

        if value_target.get('error') or value_source.get('error'):
            value_errors = []
            if value_target.get('error'):
                value_errors.append(value_target.get('error'))
            if value_source.get('error'):
                value_errors.append(value_source.get('error'))
            error_detail = '\n'.join(value_errors)
        else:
            content_source = value_source.get('content')
            content_target = value_target.get('content')
            if not isinstance(content_source, str) or not isinstance(
                    content_target, str):
                continue
            diff_text = '\n'.join(list(difflib.unified_diff(
                content_source.splitlines(),
                content_target.splitlines(),
                fromfile=source_name,
                tofile=target_name,
                lineterm='')))
            if not diff_text:
                continue
            error_detail = _colorize_diff(diff_text)

        differences += 1
        info = _format_report_info(value_target, error_detail)
        pending.append((key, info))

    for key, info in pending:
        print(t.bold('Report diff: %s' % key))
        print(info)
        print()
    return differences


def main(source, target):
    source_url = _normalize_url(source['url'])
    target_url = _normalize_url(target['url'])

    session_source = requests.Session()
    session_target = requests.Session()

    print(t.bold('Connecting to target: %s@%s' % (
        target['username'], target_url)))
    context_target = _get_context(
        target_url, target['username'], target['password'], session_target)
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
        source_url, source['username'], source['password'], session_source)
    result_source = _get_stack(
        source_url, source['username'], source['password'], context_source,
        stacks,
        session_source)

    differences = _diff_reports(
        'source', 'target', result_source, result_target)
    if not differences:
        print(t.green('No differences found.'))


def run():
    parser = ArgumentParser(
        description='Compare report stacks between two Tryton environments.')
    parser.add_argument('source',
        help='Origin env (e.g. https://user:pass@host/dbname)')
    parser.add_argument('target',
        help='Destination env (e.g. https://user:pass@host/dbname)')
    if argcomplete:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()
    try:
        source = _parse_env(args.source)
        target = _parse_env(args.target)
        main(source, target)
    except Exception as exc:
        print(t.red(str(exc)), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    run()
