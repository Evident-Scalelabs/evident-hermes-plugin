"""Real rendered fixture, controls and frozen replay; no model calls or mocks."""
import argparse
import asyncio
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading

from test_evidence import Store
from evidence_candidate.browser import observe_browser
from evidence_candidate.demo import CHANGES, demo_plan, fixture_pages
from evidence_candidate.evidence import screenshot_data, verify


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt-dir', type=Path, required=True)
    parser.add_argument('--browser-server', default='')
    args = parser.parse_args()
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp) / 'site'; site.mkdir()
        for name, text in fixture_pages().items(): (site / name).write_text(text)
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(site)))
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        try:
            store = Store((Path(tmp) / 'data').resolve())
            origin = f'http://127.0.0.1:{server.server_port}'
            plan = demo_plan(origin)
            before = await observe_browser(store, plan, [], origin, browser_server_url=args.browser_server)
            assert before['state'] == 'complete', before
            baseline = store.inspect(before['run_id'])
            assert len(baseline['steps']) == 7
            assert sum(a['passed'] is False for s in baseline['steps'] for a in s['assertions']) == 3
            assert all(s['interaction']['confirmed'] for s in baseline['steps'] if s.get('interaction'))
            assert len([s for s in baseline['steps'] if s.get('interaction')]) == 3
            assert CHANGES[2]['before'] not in baseline['steps'][4]['source_text']
            assert CHANGES[2]['before'] in baseline['steps'][6]['source_text']
            for change in CHANGES:
                file = site / change['file']; file.write_text(file.read_text().replace(change['before'], change['after']))
            after = await verify(store, before['run_id'], 'Authorized fixture edits; no criteria changes', [], origin, browser_server_url=args.browser_server)
            assert after['state'] == 'complete', after
            revised = store.inspect(after['run_id'])
            assert baseline['plan'] == revised['plan'] == plan
            assert after['verification']['comparable']
            assert sum(t['transition'] == 'met_after' for t in after['verification']['transitions']) == 3
            assert all(t['verified'] and t['after'] is True for t in after['verification']['transitions'])
            assert all(screenshot_data(s)[0] for s in baseline['steps'] + revised['steps'])
            args.receipt_dir.mkdir(parents=True, exist_ok=True)
            for label, record in [('before', baseline), ('after', revised)]:
                (args.receipt_dir / (label+'.json')).write_text(json.dumps(record))
            receipt = {'collection': 'real isolated Chromium', 'model': 'not run', 'assertions': len(after['verification']['transitions']), 'resolved': 3, 'controls_per_capture': 3, 'screenshots': 14, 'same_plan': True, 'comparable': True}
            (args.receipt_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2))
            print(json.dumps(receipt))
        finally:
            server.shutdown(); server.server_close(); worker.join(timeout=2)
            assert not worker.is_alive(), 'Fixture cleanup failed'


if __name__ == '__main__':
    asyncio.run(main())
