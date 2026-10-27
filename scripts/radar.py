#!/usr/bin/env python3
"""Offline dossier checks; never authenticates evidence or authorizes spending."""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

STATUSES = {'VERIFIED', 'COUNTERPARTY_CLAIM', 'ESTIMATE', 'HYPOTHESIS', 'UNKNOWN', 'REJECTED'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def date(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), 'expected YYYY-MM-DD')
    return dt.date.fromisoformat(value)


def unique_rows(rows, label):
    require(isinstance(rows, list), label + ' must be an array')
    result = {}
    for row in rows:
        require(isinstance(row, dict) and text(row.get('id')), label + ' requires id')
        require(row['id'] not in result, label + ' duplicate id: ' + row['id'])
        result[row['id']] = row
    return result


def independent_origins(refs, evidence):
    # 同源、同URL或同快照任一关联都归为一组，避免改名制造独立证据。
    groups = []
    for eid in refs:
        row = evidence[eid]
        keys = {('origin', row['origin_id']), ('url', row['source_url'])}
        if row.get('snapshot_sha256'):
            keys.add(('hash', row['snapshot_sha256']))
        overlaps = [g for g in groups if g & keys]
        for group in overlaps:
            keys |= group
            groups.remove(group)
        groups.append(keys)
    return len(groups)


def validate(dossier, as_of):
    """Validate declared metadata. Content truth and independence need human review."""
    require(isinstance(dossier, dict), 'dossier must be an object')
    require(type(dossier.get('schema_version')) is int and dossier['schema_version'] == 1, 'schema_version must be 1')
    business = dossier.get('business')
    require(isinstance(business, dict), 'business must be an object')
    for key in ('name', 'region', 'currency'):
        require(text(business.get(key)), 'business requires ' + key)
    require(bool(re.fullmatch(r'[A-Z]{3}', business['currency'])), 'currency requires three uppercase letters')
    cutoff = date(as_of)
    evidence = unique_rows(dossier.get('evidence'), 'evidence')
    claims = unique_rows(dossier.get('claims'), 'claims')
    blockers, warnings, usable = [], [], set()
    for eid, row in evidence.items():
        for key in ('publisher', 'source_url', 'period', 'region', 'metric', 'unit', 'origin_id', 'locator'):
            require(text(row.get(key)), eid + ' requires ' + key)
        url = urlsplit(row['source_url'])
        require((url.scheme == 'https' and bool(url.hostname) and not url.username and not url.password)
                or bool(re.fullmatch(r'urn:offline:[a-zA-Z0-9_-]+', row['source_url'])), eid + ' invalid source_url')
        require(row.get('status') in STATUSES, eid + ' invalid status')
        published, retrieved, expiry = (date(row.get(k)) for k in ('published_at', 'retrieved_at', 'expires_at'))
        require(published <= retrieved and published <= expiry, eid + ' invalid timestamp ordering')
        if row['status'] == 'VERIFIED':
            require(isinstance(row.get('snapshot_sha256'), str) and bool(re.fullmatch(r'[a-f0-9]{64}', row['snapshot_sha256'])), eid + ' requires snapshot_sha256')
        fresh = retrieved <= cutoff <= expiry
        relevant = row['region'] == business['region']
        if not fresh:
            warnings.append(eid + ': unavailable at cutoff or expired')
        if not relevant:
            warnings.append(eid + ': regional applicability needs human review')
        if fresh and relevant and row['status'] == 'VERIFIED':
            usable.add(eid)
    critical_count = 0
    for cid, row in claims.items():
        require(text(row.get('text')) and type(row.get('critical')) is bool, cid + ' requires text and critical boolean')
        require(row.get('stance') in {'support', 'counter'}, cid + ' invalid stance')
        refs = row.get('evidence_ids')
        require(isinstance(refs, list) and all(text(x) for x in refs), cid + ' requires evidence_ids array')
        require(len(refs) == len(set(refs)), cid + ' duplicate evidence reference')
        require(all(x in evidence for x in refs), cid + ' dangling evidence reference')
        eligible = set(refs) & usable
        if row['stance'] == 'counter' and eligible:
            blockers.append(cid + ': unresolved verified counterevidence')
        if row['critical']:
            critical_count += 1
            if independent_origins(eligible, evidence) < 2:
                blockers.append(cid + ': needs two fresh relevant independent declared origins')
    if not critical_count:
        blockers.append('no critical decision claim')
    scenarios = dossier.get('scenarios')
    require(isinstance(scenarios, list), 'scenarios must be an array')
    cash, names, periods = [], set(), set()
    for row in scenarios:
        require(isinstance(row, dict) and text(row.get('name')), 'scenario requires name')
        require(row['name'] not in names, 'duplicate scenario name')
        names.add(row['name'])
        require(row.get('currency') == business['currency'], 'scenario currency must match business currency; convert explicitly before comparison')
        period = row.get('period')
        require(isinstance(period, str) and bool(re.fullmatch(r'\d{4}-\d{2}/\d{4}-\d{2}', period)), 'scenario period requires YYYY-MM/YYYY-MM')
        start, end = (date(month + '-01') for month in period.split('/'))
        require(start <= end, 'scenario period ends before start')
        periods.add(period)
        for key in ('opening_cash', 'revenue', 'cost', 'capex', 'working_capital', 'reserve'):
            v = row.get(key)
            require(type(v) in (int, float) and math.isfinite(v) and v >= 0, 'scenario requires finite nonnegative ' + key)
        net = row['opening_cash'] + row['revenue'] - row['cost'] - row['capex'] - row['working_capital'] - row['reserve']
        require(math.isfinite(net), 'scenario cash overflow')
        cash.append({'name': row['name'], 'period': period, 'cash_after_reserve': round(net, 2), 'currency': row['currency']})
        if net < 0:
            blockers.append(row['name'] + ': cash below reserve')
    if len(scenarios) < 3:
        blockers.append('need at least three distinct comparable cash scenarios')
    if len(periods) > 1:
        blockers.append('scenario periods differ; normalize before comparison')
    return {'schema_version': 1, 'as_of': as_of,
            'readiness': 'EVIDENCE_INCOMPLETE' if blockers else 'READY_FOR_HUMAN_REVIEW',
            'blockers': blockers, 'warnings': warnings, 'cash_scenarios': cash,
            'limitations': 'Metadata checks only; origins, snapshots, source meaning, policy eligibility and scenario assumptions need human verification. No spending or investment authorization.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate'])
    parser.add_argument('dossier', type=Path)
    parser.add_argument('--as-of', required=True)
    args = parser.parse_args(argv)
    try:
        result = validate(json.loads(args.dossier.read_text(encoding='utf-8')), args.as_of)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result['blockers'] else 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
