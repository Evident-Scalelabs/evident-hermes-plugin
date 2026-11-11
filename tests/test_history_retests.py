"""Contract tests with synthetic records; real Hermes/browser acceptance is separate."""
import asyncio
import copy
from pathlib import Path
import tempfile
import unittest

from test_evidence import Store
from evidence_candidate.contextual import compare_answers
from evidence_candidate.retests import evaluate, save_test, verify_test


URL = "https://example.com/pricing"


def fixture(store):
    plan = {"mode": "browser", "objective": "Choose a five-person plan", "viewport": {"width": 1280, "height": 800},
            "steps": [{"action": "open", "url": URL, "assertions": []}],
            "limits": {"seconds": 30, "resources": 50, "bytes_per_resource": 100000}}
    run = store.create(plan)
    element = {"text": "$29 per team", "text_origin": "rendered_text", "text_truncated": False,
               "identity": {"selector": "#price", "tag": "P", "page_heading": "Team plan",
                            "region_heading": "Pricing", "siblings": "H2,P"}}
    store.write(run, "step-0.json", {"index": 0, "state": "observed", "fetched_url": URL,
                                     "elements": [element], "controls": [], "assertions": []})
    store.write(run, "result.json", {"state": "complete", "environment": {"test": True}})
    store.write(run, "review.json", {"summary": "A synthetic price conflict", "notes": [
        {"title": "Clarify the team price", "step": 0, "element": 0, "quote": "$29 per team", "related_evidence": []}]})
    return run


class HistoryTests(unittest.TestCase):
    def test_fresh_store_recalls_revisions_and_profile_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Store(Path(tmp).resolve() / "first")
            with first.history() as history:
                history.remember(URL, "goal", "goal", "Choose a five-person plan")
                history.remember(URL, "billing", "fact", "Monthly billing")
                history.remember(URL, "billing", "fact", "Annual billing")
                history.remember(URL, "billing", "fact", "Annual billing")
            with Store(first.root).history() as history:
                recalled = history.recall("https://example.com/")
                self.assertEqual(recalled["revision"], 3)
                self.assertEqual([i["value"] for i in recalled["items"]], ["Annual billing", "Choose a five-person plan"])
                self.assertTrue(all(i["provenance"] == "user_confirmed" for i in recalled["items"]))
                history.forget(URL, "billing")
                self.assertEqual([i["key"] for i in history.recall(URL)["items"]], ["goal"])
            with Store(Path(tmp).resolve() / "other").history() as history:
                self.assertEqual(history.recall(URL)["items"], [])

    def test_deleted_evidence_is_marked_and_site_forgetting_preserves_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve())
            run = fixture(store)
            with store.history() as history:
                history.remember(URL, "pricing", "fact", "Confirmed price", source_run=run)
                history.record_run(URL, store.inspect(run), 1)
            store.delete(run)
            with store.history() as history:
                self.assertFalse(history.recall(URL)["items"][0]["source_available"])
                self.assertFalse(history.recall(URL)["runs"][0]["source_available"])
            run = fixture(store)
            with store.history() as history:
                history.forget(URL)
                self.assertEqual(history.recall(URL)["items"], [])
                self.assertEqual(history.recall(URL)["runs"], [])
            self.assertEqual(store.inspect(run)["result"]["state"], "complete")

    def test_fact_cannot_claim_a_different_site_as_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve())
            run = fixture(store)
            with store.history() as history, self.assertRaisesRegex(ValueError, "another site"):
                history.remember("https://other.example/", "fact", "fact", "Unknown", source_run=run)

    def test_goal_needs_no_key_and_only_facts_change_the_saved_test_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            with Store(Path(tmp).resolve()).history() as history:
                history.remember(URL, "billing", "fact", "Annual billing")
                facts, revision = history.facts_digest(URL), history.comparison_revision(URL)
                self.assertEqual(history.remember(URL, None, "goal", "Choose a plan")["key"], "goal")
                history.remember(URL, "rival", "competitor", {"name": "Rival", "url": "https://rival.example/",
                                                              "disposition": "exclude", "reason": "Another market"})
                history.forget(URL, "rival")
                self.assertEqual(history.facts_digest(URL), facts)
                self.assertGreater(history.comparison_revision(URL), revision)
                self.assertEqual(history.comparison_revision(URL), history.recall(URL)["comparison_revision"])
                history.remember(URL, "billing", "fact", "Monthly billing")
                self.assertNotEqual(history.facts_digest(URL), facts)
                history.remember(URL, "billing", "fact", "Annual billing")
                self.assertEqual(history.facts_digest(URL), facts)

    def test_recalled_retest_retains_its_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve())
            run = fixture(store)
            record = store.inspect(run)
            record["retest"] = {"test_id": "a"*32, "definition": {"title": "Confirm the team price"},
                                "after": {"status": "failed"}}
            with store.history() as history:
                history.record_run(URL, record, 0)
                recalled = history.recall(URL)["runs"][0]
            self.assertEqual(recalled["state"], "failed")
            self.assertIn("Confirm the team price", recalled["summary"])


class RetestTests(unittest.TestCase):
    def test_frozen_statement_rejects_wrong_region_contradiction_and_ambiguous_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve())
            run = fixture(store)
            saved = save_test(store, run, 0, [{"step": 0, "element": 0, "expected_text": "$145 per team"}], True)
            definition = saved["definition"]
            self.assertEqual(saved["baseline"]["status"], "failed")
            record = store.inspect(run)
            other = copy.deepcopy(record["steps"][0]["elements"][0])
            other["text"] = "$145 per team"
            other["identity"]["selector"] = "#other-product"
            record["steps"][0]["elements"].append(other)
            self.assertEqual(evaluate(definition, record)["status"], "failed")
            record["steps"][0]["elements"][0]["text"] = "$145 per team. Still $29 per team."
            self.assertEqual(evaluate(definition, record)["status"], "failed")
            record["steps"][0]["elements"][0]["text"] = "  $145  per team\n"
            self.assertEqual(evaluate(definition, record)["status"], "passed")
            record["steps"][0]["elements"].append(copy.deepcopy(record["steps"][0]["elements"][0]))
            self.assertEqual(evaluate(definition, record)["status"], "inconclusive")
            self.assertEqual(definition["criteria"][0]["expected_text"], "$145 per team")

    def test_missing_changed_and_truncated_sources_are_inconclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve())
            run = fixture(store)
            saved = save_test(store, run, 0, [{"step": 0, "element": 0, "expected_text": "$145 per team"}], True)
            for change in ("missing_page", "missing_element", "changed_product", "changed_controls", "truncated"):
                with self.subTest(change=change):
                    record = store.inspect(run)
                    step = record["steps"][0]
                    if change == "missing_page":
                        step["state"] = "failed"
                    elif change == "missing_element":
                        step["elements"] = []
                    elif change == "changed_product":
                        step["elements"][0]["identity"]["page_heading"] = "Another product"
                    elif change == "changed_controls":
                        step["controls"] = [{"kind": "tab", "selector": "#annual", "active": True}]
                    else:
                        step["elements"][0]["text_truncated"] = True
                    self.assertEqual(evaluate(saved["definition"], record)["status"], "inconclusive")

    def test_confirmed_heading_correction_keeps_the_source_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve())
            run = fixture(store)
            saved = save_test(store, run, 0, [{"step": 0, "element": 0, "expected_text": "$145 per team"}], True)
            record = store.inspect(run)
            element = record["steps"][0]["elements"][0]
            # The corrected element is itself the page heading, so its own identity carries the new text.
            element["text"] = element["identity"]["page_heading"] = " $145  per team"
            self.assertEqual(evaluate(saved["definition"], record)["status"], "passed")
            element["identity"]["siblings"] = "H2,P,P"
            self.assertEqual(evaluate(saved["definition"], record)["status"], "inconclusive")

    def test_confirmation_and_evidence_identity_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve())
            run = fixture(store)
            criteria = [{"step": 0, "element": 0, "expected_text": "$145 per team"}]
            with self.assertRaisesRegex(ValueError, "Confirm"):
                save_test(store, run, 0, criteria, False)
            with self.assertRaisesRegex(ValueError, "cited"):
                save_test(store, run, 0, [{**criteria[0], "element": 2}], True)
            saved = save_test(store, run, 0, criteria, True)
            with store.history() as history:
                history.remember(URL, "billing", "fact", "New product conditions")
            result = asyncio.run(verify_test(store, saved["test_id"], "Changed pricing", [], ""))
            self.assertEqual(result["state"], "inconclusive")


class ComparisonTests(unittest.TestCase):
    def test_question_route_settings_and_context_changes_are_incomparable(self):
        answer = {"index": 0, "state": "answered", "question": {"question": "What does a team pay?"},
                  "provider": "test", "model": "model-a", "sampling": {"temperature": 0},
                  "parsed": {"answer": "$145", "references": [{"url": URL}]}}
        old = {"objective": "Choose a plan", "site_revision": 0, "answers": [answer]}
        current = copy.deepcopy(old)
        self.assertTrue(compare_answers(old, current, "baseline")["rows"][0]["comparable"])
        for key, value in (("question", {"question": "Other question"}), ("model", "model-b"), ("sampling", {})):
            current = copy.deepcopy(old)
            current["answers"][0][key] = value
            self.assertFalse(compare_answers(old, current, "baseline")["rows"][0]["comparable"])
        current = copy.deepcopy(old)
        current["site_revision"] = 1
        self.assertIn("context changed", compare_answers(old, current, "baseline")["rows"][0]["reason"])
