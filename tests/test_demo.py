"""Demo failure and reporting contracts; these mocks do not prove integration."""
import asyncio
import copy
import json
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from test_evidence import Store
from evidence_candidate import register
from evidence_candidate.commands import chat_summary
from evidence_candidate.demo import CHANGES, GOAL, demo_plan, run_demo
from evidence_candidate.evidence import compare
from evidence_candidate.report import render


class DemoTests(unittest.TestCase):
    def test_native_demo_refuses_targets_and_respects_both_operator_settings(self):
        handlers, settings = {}, {}
        with tempfile.TemporaryDirectory() as tmp:
            ctx = SimpleNamespace(register_tool=lambda **tool: handlers.update({tool["name"]: tool["handler"]}),
                register_command=lambda *a, **kw: None, register_cli_command=lambda *a, **kw: None,
                register_skill=lambda *a: None, register_hook=lambda *a: None, get_config=lambda key, default=None: settings.get(key, default))
            with patch.dict(sys.modules, {"plugins.plugin_storage": SimpleNamespace(plugin_data_dir=lambda name: Path(tmp).resolve())}):
                register(ctx)
            for args, config, expected in [
                    ({"url": "https://example.com"}, {"browser_enabled": True, "allow_model_interpretation": True}, "no arguments"),
                    ({}, {"allow_model_interpretation": True}, "browser_enabled"),
                    ({}, {"browser_enabled": True}, "allow_model_interpretation")]:
                with self.subTest(expected=expected):
                    settings.clear(); settings.update(config)
                    result = json.loads(asyncio.run(handlers["evident_demo"](args)))
                    self.assertEqual(result["state"], "unavailable")
                    self.assertIn(expected, result["detail"])
                    self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_report_keeps_unknown_and_incomparable_outcomes_visible(self):
        plan = demo_plan('http://127.0.0.1:12345')
        before = {'run_id': 'a'*32, 'plan': plan, 'result': {'environment': {'version': 'one'}}, 'steps': [
            {'index': i, 'action': s['action'], 'state': 'observed', 'assertions': [{**a, 'passed': not any(c['step'] == i and c['after'] == a['expected'] for c in CHANGES)} for a in s['assertions']]} for i, s in enumerate(plan['steps'])]}
        after = copy.deepcopy(before); after['run_id'] = 'b'*32
        for s in after['steps']:
            for a in s['assertions']: a['passed'] = True
        after['result']['verification'] = compare(before, after)
        after['demo'] = {'before': before['run_id'], 'after': after['run_id'], 'changes': list(CHANGES), 'state': 'complete', 'goal': GOAL, 'context': 'Fictional fixture'}
        html = render(after, before)
        self.assertIn('3 / 3', html)
        self.assertEqual(html.count('class="demo-card"'), 3)
        self.assertIn('model finding unavailable', html)
        after['result']['environment']['version'] = 'different'
        after['result']['verification'] = compare(before, after)
        html = render(after, before)
        self.assertIn('0 / 3', html)
        self.assertNotIn('Verified change', html)
        self.assertIn('Comparable before-and-after conditions were not established', html)
        after['result']['environment'] = before['result']['environment']
        after['steps'] = after['steps'][:2]
        after['result']['verification'] = compare(before, after)
        html = render(after, before)
        self.assertIn('This capture is unavailable', html)
        self.assertIn('unknown', html)

    def test_model_failure_preserves_baseline_without_applying_changes(self):
        async def capture(store, plan, *args, **kwargs):
            run_id = store.create(plan)
            result = {'run_id': run_id, 'state': 'complete', 'observed_steps': 0}
            store.write(run_id, 'result.json', result)
            return result
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve())
            ctx = SimpleNamespace(get_config=lambda key, default=None: True if key in ('browser_enabled', 'allow_model_interpretation') else default)
            with patch('evidence_candidate.demo.observe_browser', capture), patch('evidence_candidate.demo.review_capture', AsyncMock(side_effect=ValueError('Unsupported citation'))), patch('evidence_candidate.demo.verify', AsyncMock()) as verifier:
                result = asyncio.run(run_demo(ctx, store))
            self.assertEqual(result['state'], 'partial')
            verifier.assert_not_called()
            receipt = store.inspect(result['run_id'])['demo']
            self.assertEqual(receipt['changes'], [])
            self.assertEqual(receipt['fixture_cleanup'], 'stopped')
            message = chat_summary(result)
            self.assertEqual(result['delivery'], 'MEDIA:' + result['view'])
            self.assertEqual(message.count('MEDIA:'), 1)
            self.assertNotIn('<html', message)
            self.assertNotIn('complete.', message)
            store.delete(result['run_id'])


if __name__ == '__main__':
    unittest.main()
