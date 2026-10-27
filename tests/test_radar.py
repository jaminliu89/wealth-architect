"""All financial/source data here are synthetic fixtures, never market evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('radar', ROOT / 'scripts/radar.py')
radar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(radar)


def fixture():
    evidence = []
    for n in range(2):
        evidence.append(dict(id=f'e{n}', source_url=f'https://example.org/{n}', publisher='SYNTHETIC',
            published_at='2026-01-01', retrieved_at='2026-01-02', expires_at='2026-12-31',
            period='2025 annual', region='TEST', metric='orders', unit='count', status='VERIFIED',
            origin_id=f'origin-{n}', locator='synthetic table 1',
            snapshot_sha256=hashlib.sha256(f'synthetic-{n}'.encode()).hexdigest()))
    return dict(schema_version=1, business=dict(name='SYNTHETIC', region='TEST', currency='CNY'),
        evidence=evidence,
        claims=[dict(id='c1', text='SYNTHETIC decision hypothesis', evidence_ids=['e0', 'e1'], critical=True, stance='support')],
        scenarios=[dict(name=n, period='2026-01/2026-12', currency='CNY', opening_cash=0, revenue=r, cost=20, capex=10, working_capital=10, reserve=10)
                   for n, r in [('downside', 60), ('base', 80), ('upside', 100)]])


class RadarTests(unittest.TestCase):
    def setUp(self):
        self.d = fixture()

    def check(self):
        return radar.validate(self.d, '2026-10-28')

    def test_metadata_ready_is_not_authorization(self):
        r = self.check()
        self.assertEqual(r['readiness'], 'READY_FOR_HUMAN_REVIEW')
        self.assertIn('No spending', r['limitations'])
        self.assertEqual(r['cash_scenarios'][0]['cash_after_reserve'], 10)

    def test_duplicate_origins_not_independent(self):
        self.d['evidence'][1]['origin_id'] = 'origin-0'
        self.assertEqual(self.check()['readiness'], 'EVIDENCE_INCOMPLETE')

    def test_relabelled_duplicate_url_or_hash_is_not_independent(self):
        for field in ['source_url', 'snapshot_sha256']:
            self.d = fixture()
            self.d['evidence'][1][field] = self.d['evidence'][0][field]
            self.assertTrue(self.check()['blockers'])

    def test_transitively_related_sources_are_not_independent(self):
        self.d['evidence'].append(copy.deepcopy(self.d['evidence'][0]))
        self.d['evidence'][2].update(id='e2', origin_id='origin-1')
        self.d['claims'][0]['evidence_ids'].append('e2')
        self.assertTrue(self.check()['blockers'])

    def test_mixed_scenario_currency_rejected(self):
        self.d['scenarios'][0]['currency'] = 'USD'
        with self.assertRaises(ValueError):
            self.check()

    def test_mixed_scenario_period_blocks(self):
        self.d['scenarios'][0]['period'] = '2026-01/2026-01'
        self.assertTrue(self.check()['blockers'])

    def test_missing_or_invalid_scenario_period_rejected(self):
        for value in [None, 'annual', '2026-00/2026-12', '2026-12/2026-01']:
            self.d = fixture()
            self.d['scenarios'][0]['period'] = value
            with self.assertRaises(ValueError):
                self.check()

    def test_expiry_blocks_critical_claim(self):
        self.d['evidence'][0]['expires_at'] = '2026-02-01'
        self.assertTrue(self.check()['blockers'])

    def test_expired_material_can_be_retrieved_and_retained(self):
        self.d['evidence'][0].update(retrieved_at='2026-10-28', expires_at='2026-09-30', status='REJECTED')
        self.assertTrue(self.check()['blockers'])
        self.assertTrue(self.check()['warnings'])

    def test_future_information_cannot_leak_into_backtest(self):
        self.d['evidence'][0]['retrieved_at'] = '2026-11-01'
        self.assertTrue(self.check()['blockers'])

    def test_unverified_statuses_do_not_support_decision(self):
        for status in radar.STATUSES - {'VERIFIED'}:
            with self.subTest(status=status):
                self.d = fixture()
                self.d['evidence'][0]['status'] = status
                self.assertTrue(self.check()['blockers'])

    def test_wrong_region_requires_review(self):
        self.d['evidence'][0]['region'] = 'OTHER'
        self.assertTrue(self.check()['blockers'])
        self.assertTrue(self.check()['warnings'])

    def test_verified_counterevidence_blocks(self):
        self.d['claims'].append(dict(id='c2', text='counter', critical=False, stance='counter', evidence_ids=['e0']))
        self.assertIn('counterevidence', ' '.join(self.check()['blockers']))

    def test_cash_below_reserve_blocks(self):
        self.d['scenarios'][0]['revenue'] = 1
        self.assertIn('cash below', ' '.join(self.check()['blockers']))

    def test_opening_cash_covers_initial_investment(self):
        self.d['scenarios'][0].update(opening_cash=100, revenue=0)
        self.assertEqual(self.check()['cash_scenarios'][0]['cash_after_reserve'], 50)
        self.assertFalse(self.check()['blockers'])

    def test_missing_stress_scenarios_blocks(self):
        self.d['scenarios'] = []
        self.assertTrue(self.check()['blockers'])

    def test_no_critical_claim_blocks(self):
        self.d['claims'] = []
        self.assertTrue(self.check()['blockers'])

    def test_offline_evidence_location_supported(self):
        self.d['evidence'][0]['source_url'] = 'urn:offline:authorized-ledger'
        self.assertFalse(self.check()['blockers'])

    def test_bad_dates_rejected(self):
        for value in ['2026-02-30', '2026-1-1', None]:
            with self.subTest(value=value):
                self.d = fixture()
                self.d['evidence'][0]['published_at'] = value
                with self.assertRaises(ValueError):
                    self.check()

    def test_bad_date_order_rejected(self):
        self.d['evidence'][0]['published_at'] = '2026-11-01'
        with self.assertRaises(ValueError):
            self.check()

    def test_dangling_reference_rejected(self):
        self.d['claims'][0]['evidence_ids'] = ['absent']
        with self.assertRaises(ValueError):
            self.check()

    def test_duplicate_ids_and_refs_rejected(self):
        for field in ['evidence', 'claims']:
            self.d = fixture()
            self.d[field].append(copy.deepcopy(self.d[field][0]))
            with self.assertRaises(ValueError):
                self.check()
        self.d = fixture()
        self.d['claims'][0]['evidence_ids'] = ['e0', 'e0']
        with self.assertRaises(ValueError):
            self.check()

    def test_bad_numeric_inputs_rejected(self):
        for value in [True, float('nan'), float('inf'), -1, '10', None]:
            with self.subTest(value=value):
                self.d = fixture()
                self.d['scenarios'][0]['revenue'] = value
                with self.assertRaises(ValueError):
                    self.check()

    def test_url_and_snapshot_validation(self):
        for url in ['http://example.org', 'https://user:password@example.org', 'file:///private/data', 'javascript:alert(1)']:
            self.d = fixture()
            self.d['evidence'][0]['source_url'] = url
            with self.assertRaises(ValueError):
                self.check()
        self.d = fixture()
        self.d['evidence'][0]['snapshot_sha256'] = 'placeholder'
        with self.assertRaises(ValueError):
            self.check()

    def test_empty_input_rejected(self):
        with self.assertRaises(ValueError):
            radar.validate({}, '2026-10-28')

    def test_cli_codes_and_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dossier.json'
            for expected, value in [(0, fixture()), (2, dict(fixture(), claims=[])), (1, {})]:
                path.write_text(json.dumps(value))
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/radar.py'), 'validate', str(path), '--as-of', '2026-10-28'], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stdout)
                self.assertIsInstance(json.loads(result.stdout), dict)
            path.write_text('{')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/radar.py'), 'validate', str(path), '--as-of', '2026-10-28'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)


class DistributionTests(unittest.TestCase):
    def test_skill_frontmatter_and_resources(self):
        body = (ROOT / 'SKILL.md').read_text()
        self.assertTrue(body.startswith('---\nname: wealth-architect\n'))
        self.assertLess(len(body.splitlines()), 500)
        for name in ['evidence-model.md', 'data-sources.md', 'report-template.md']:
            self.assertTrue((ROOT / 'references' / name).is_file(), name)


if __name__ == '__main__':
    unittest.main()
