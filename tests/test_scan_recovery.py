"""Exercise the registered tools, real file locks and deadlines with no external calls."""
import asyncio
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from test_evidence import Store
from evidence_candidate import INTAKE, register


URL = "https://credit.example/"
GOAL = "Decide whether to join."


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.store = Store(self.root)
        self.tools, self.hooks, self.sections = {}, {}, {}
        ctx = SimpleNamespace(
            register_tool=lambda **t: self.tools.update({t["name"]: t["handler"]}),
            register_hook=lambda name, fn: self.hooks.update({name: fn}),
            register_system_prompt_section=lambda name, content: self.sections.update({name: content}),
            register_command=lambda *a, **kw: None, register_cli_command=lambda *a, **kw: None,
            register_skill=lambda *a: None,
            get_config=lambda key, default=None: True if key in ("browser_enabled", "allow_model_interpretation") else default)
        self.enterContext(patch.dict(sys.modules, {"plugins.plugin_storage": SimpleNamespace(
            plugin_data_dir=lambda name: self.root,
            plugin_db=lambda name, file: sqlite3.connect(self.root / file))}))
        register(ctx)
        self.enterContext(patch("evidence_candidate.interpretation.resolve_scan_url", return_value=(URL, URL.rstrip("/"), [])))

    def inspect(self, **args):
        return json.loads(self.tools["evident_inspect"](args))

    async def scan(self, capture, budget=10):
        with patch("evidence_candidate.interpretation.chat_work_budget", return_value=budget), \
             patch("evidence_candidate.browser.observe_browser", capture):
            return json.loads(await self.tools["evident_scan"]({"url": URL, "objective": GOAL}))

    def step(self, store, run_id):
        store.write(run_id, "step-0.json", {"index": 0, "state": "observed", "action": "open", "fetched_url": URL,
                    "source_text": "Membership requirements", "elements": [], "assertions": []})

    def test_routing_intake_and_no_actions(self):
        self.assertIn(INTAKE, self.sections.values())
        hook = self.hooks["pre_llm_call"]
        for message in ("Is this evident?", "Is my website evident?", "Evident, review this: " + URL):
            self.assertEqual(hook(user_message=message, conversation_history=["We discussed ParlayTix."]), {"context": INTAKE})
        for message in ("Are you Hermes or Evident?", "Evident is our brand.", "Is this evident in the proof?"):
            self.assertIsNone(hook(user_message=message))
        self.assertEqual(list(self.root.iterdir()), [])

    async def test_real_deadline_and_read_only_running_and_partial_recovery(self):
        entered = asyncio.Event()
        async def capture(store, plan, origins, run_id, **kw):
            self.step(store, run_id)
            entered.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(self.scan(capture, budget=0.35))
        await asyncio.wait_for(entered.wait(), 2)
        active = self.inspect(url=URL)
        self.assertEqual((active["state"], active["objective"], active["retained_steps"]), ("running", GOAL, 1))
        self.assertNotIn("delivery", active)
        done = await task
        self.assertEqual((done["state"], done["run_id"]), ("partial", active["run_id"]))
        recovered = self.inspect(url=URL)
        self.assertEqual(recovered["delivery"], "MEDIA:" + done["view"])
        self.assertIn("Partial report", Path(done["view"]).read_text())
        self.assertIn("Membership requirements", Path(done["view"]).read_text())
        self.assertEqual(self.inspect(url="https://different.example/")["error"], "not_found")

    async def test_explicit_cancellation_is_recoverable(self):
        entered = asyncio.Event()
        async def capture(store, plan, origins, run_id, **kw):
            self.step(store, run_id)
            entered.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(self.scan(capture))
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        result = self.inspect(url=URL)
        self.assertEqual(result["state"], "cancelled")
        self.assertIn("Partial report", Path(result["view"]).read_text())

    async def test_website_checkpoint_and_idempotent_continuation(self):
        async def capture(store, plan, origins, run_id, **kw):
            self.step(store, run_id)
            result = {"run_id": run_id, "state": "complete", "observed_steps": 1, "requests": [], "limitations": []}
            store.write(run_id, "result.json", result)
            return result
        async def review(ctx, store, run_id, receipt):
            receipt.update(state="complete", pages_observed=1, screenshots=0)
            store.write(run_id, "review.json", {"summary": "Fixture website review.", "notes":[]})
        async def collect(ctx, store, run_id, **kw):
            value = {"state":"complete","answers":[],"sources":[],"plan":None,"comparison":None}
            store.write(run_id, "context.json", value)
            return value
        with patch("evidence_candidate.interpretation.review_capture", review), \
             patch("evidence_candidate.contextual.collect", new=AsyncMock(side_effect=collect)) as paid:
            start = await self.scan(capture)
            run = start["run_id"]
            self.assertEqual(start["next_tool"], {"name":"evident_finish", "arguments":{"run_id":run}})
            preview = self.inspect(url=URL)
            self.assertEqual(preview["stage"], "awaiting_context")
            self.assertIn("Partial report", Path(preview["view"]).read_text())
            paid.assert_not_awaited()
            args = {"run_id":run}
            first = json.loads(await self.tools["evident_finish"](args))
            second = json.loads(await self.tools["evident_finish"](args))
            self.assertEqual((first["state"], first["delivery"]), ("complete", second["delivery"]))
            self.assertNotEqual(preview["view"], first["view"])
            self.assertNotIn("Partial report", Path(first["view"]).read_text())
            paid.assert_awaited_once()
            # Simulate abrupt process death after a paid comparison was admitted.
            start = await self.scan(capture)
            run = start["run_id"]
            self.store.write(run, "context-started.json", {"started": "fixture"})
            self.assertEqual(self.inspect(url=URL)["stage"], "checking_answers")
            crashed = json.loads(await self.tools["evident_finish"]({"run_id":run}))
            self.assertEqual((crashed["state"],crashed["context_state"]), ("partial","interrupted"))
            paid.assert_awaited_once()

    def test_lookup_corrupt_and_missing_records(self):
        self.assertEqual(self.inspect(run_id="../outside")["error"], "invalid_lookup")
        self.assertEqual(self.inspect(run_id="a"*32)["error"], "not_found")
        run = self.store.create({"objective": GOAL, "steps":[]})
        self.store.write_bytes(run, "result.json", b"not json")
        self.assertEqual(self.inspect(run_id=run)["error"], "unreadable_evidence")
