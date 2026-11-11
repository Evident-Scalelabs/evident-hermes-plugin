"""Real native Hermes + managed Chromium acceptance with a controlled website.

The fixture authors its own finding and expected statements. No model is used.
Run with the host and plugin dependencies installed, passing a Hermes source tree.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--browser-server", default="")
    args = parser.parse_args()
    args.receipt_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.upstream.resolve()))
    phase = "baseline"

    async def serve(reader, writer):
        try:
            request = await reader.readuntil(b"\r\n\r\n")
            path = request.split(b" ")[1].decode()
            price = "$145 per team" if phase in ("fixed", "missing", "ambiguous") else "$29 per team"
            if phase == "contradiction":
                price = "$145 per team. Still $29 per team."
            duplicate = '<p id="price">$145 per team</p>' if phase == "ambiguous" else ''
            extra = '<p id="other-product">$145 per team</p>'
            if path == "/terms":
                content = '<h1>Team terms</h1><section><h2>Price</h2><p id="terms-price">$145 per team</p></section>'
                if phase == "missing":
                    content = '<h1>Page unavailable</h1>'
            else:
                content = '<h1>Team plan</h1><section><h2>Pricing</h2><p id="price">'+price+'</p>'+duplicate+'</section>'+extra+'<details><summary id="faq">What does the plan include?</summary><p>Five team members and offline work.</p></details><a id="terms" href="/terms">Read pricing terms</a>'
            body = ('<!doctype html><html><head><title>Controlled team plan</title><meta name="robots" content="noindex"><link rel="canonical" href="'+path+'"><style>body{font:24px system-ui;max-width:900px;margin:60px auto}section,details{padding:24px;border:1px solid #ccc;margin:20px 0}</style></head><body>'+content+'</body></html>').encode()
            status = b"404 Not Found" if phase == "missing" and path == "/terms" else b"200 OK"
            writer.write(b"HTTP/1.1 "+status+b"\r\nContent-Type: text/html\r\nContent-Length: "+str(len(body)).encode()+b"\r\nConnection: close\r\n\r\n"+body)
            await writer.drain()
        finally:
            writer.close()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    origin = "http://127.0.0.1:"+str(server.sockets[0].getsockname()[1])
    try:
        with tempfile.TemporaryDirectory(prefix="evident-saved-native-") as directory:
            home = Path(directory).resolve()
            os.environ["HERMES_HOME"] = str(home)
            os.environ["HERMES_BUNDLED_PLUGINS"] = str(home / "bundled")
            os.environ["HERMES_ENABLE_PROJECT_PLUGINS"] = "0"
            (home / "bundled").mkdir()
            destination = home / "plugins/evident-evidence"
            shutil.copytree(Path(__file__).resolve().parents[1], destination,
                            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
            (home / "config.yaml").write_text(json.dumps({"plugins": {"enabled": ["evident-evidence"],
                "entries": {"evident-evidence": {"settings": {"browser_enabled": True,
                    "fixture_origin": origin, "browser_server_url": args.browser_server}}}}}))
            from hermes_cli.plugins import PluginManager
            from tools.registry import registry
            manager = PluginManager()
            manager.discover_and_load()

            async def invoke(name, arguments):
                response = await asyncio.to_thread(registry.dispatch, name, arguments, scope=manager.scope_key)
                value = json.loads(response)
                assert value.get("state") != "unavailable", (name, value)
                return value

            try:
                await invoke("evident_memory", {"action": "remember", "url": origin, "key": "goal", "kind": "goal", "value": "Choose the five-person plan", "confirm": True})
                await invoke("evident_memory", {"action": "remember", "url": origin, "key": "billing", "kind": "fact", "value": "Monthly", "confirm": True})
                await invoke("evident_memory", {"action": "remember", "url": origin, "key": "billing", "kind": "fact", "value": "Annual", "confirm": True})
                manager.unload()
                manager = PluginManager()
                manager.discover_and_load()
                recalled = await invoke("evident_memory", {"action": "recall", "url": origin})
                assert {item["key"]: item["value"] for item in recalled["items"]} == {"goal": "Choose the five-person plan", "billing": "Annual"}
                other = home / "other-profile"
                other.mkdir()
                os.environ["HERMES_HOME"] = str(other)
                assert (await invoke("evident_memory", {"action": "recall", "url": origin}))["items"] == []
                os.environ["HERMES_HOME"] = str(home)
                plan = {"mode": "browser", "objective": "Choose the five-person plan", "viewport": {"width": 1280, "height": 900},
                        "limits": {"seconds": 45, "resources": 30, "bytes_per_resource": 100000}, "steps": [
                            {"action": "open", "url": origin+"/", "assertions": []},
                            {"action": "activate_control", "control": {"kind": "disclosure", "selector": "#faq", "text": "What does the plan include?", "group": ""}, "assertions": [{"kind": "control_active", "expected": True}]},
                            {"action": "follow_link", "selector": "#terms", "assertions": []}]}
                baseline = await invoke("evident_browse", {"plan": plan})
                assert baseline["state"] == "complete", baseline
                inspected = await invoke("evident_inspect", {"run_id": baseline["run_id"]})
                steps = inspected["record"]["steps"]
                assert steps[1]["interaction"]["confirmed"]
                assert steps[0]["document_observations"]["robots"][0]["content"] == "noindex"
                indexes = [next(i for i, element in enumerate(steps[step]["elements"]) if element["identity"]["selector"] == selector)
                           for step, selector in ((0, "#price"), (2, "#terms-price"))]
                note = {"step": 0, "element": indexes[0], "quote": "$29 per team", "title": "Make the team price consistent",
                        "observation": "The offer and terms state different team prices.", "implication": "The decision has conflicting prices.",
                        "suggested_change": "Confirm and publish the same price in both regions.", "uncertainty": "Controlled fixture only.",
                        "kind": "observed_issue", "priority": "first", "visitor_task": "Choose the team plan",
                        "priority_reason": "Price is needed for this decision.", "verification": "Both regions state $145 per team.",
                        "related_evidence": [{"step": 2, "element": indexes[1], "quote": "$145 per team"}]}
                await invoke("evident_report", {"run_id": baseline["run_id"], "review": {"summary": "Resolve the two different prices.",
                    "limitations": "Fixture-authored finding for deterministic acceptance; no model interpretation.", "journeys": [], "notes": [note]}})
                saved = await invoke("evident_save_test", {"run_id": baseline["run_id"], "finding": 0, "confirm": True,
                    "criteria": [{"step": step, "element": index, "expected_text": "$145 per team"} for step, index in zip((0, 2), indexes)]})
                assert saved["baseline"]["status"] == "failed"
                outcomes = []
                for phase, expected in (("wrong_region", "failed"), ("contradiction", "failed"), ("fixed", "passed"), ("missing", "inconclusive"), ("ambiguous", "inconclusive")):
                    result = await invoke("evident_verify", {"test_id": saved["test_id"], "change_context": "Fixture owner applied phase "+phase})
                    assert result["state"] == expected, (phase, result)
                    assert result["criteria_sha256"] == saved["definition"]["criteria_sha256"]
                    history = await invoke("evident_memory", {"action": "recall", "url": origin})
                    assert history["runs"][0]["run_id"] == result["run_id"]
                    assert history["runs"][0]["state"] == expected
                    path = Path(result["report_path"])
                    shutil.copyfile(path, args.receipt_dir / (phase+".html"))
                    outcomes.append({"phase": phase, "state": result["state"], "criteria_sha256": result["criteria_sha256"],
                                     "report_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
                    (args.receipt_dir / (phase+".json")).write_text(json.dumps(result, indent=2))
                await invoke("evident_memory", {"action": "forget", "url": origin, "key": "billing", "confirm": True})
                remaining = await invoke("evident_memory", {"action": "recall", "url": origin})
                assert [item["key"] for item in remaining["items"]] == ["goal"]
                assert remaining["tests"] and remaining["runs"]
                assert all("summary" not in run for run in remaining["runs"])
                await invoke("evident_memory", {"action": "forget", "url": origin, "confirm": True})
                forgotten = await invoke("evident_memory", {"action": "recall", "url": origin})
                assert not forgotten["items"] and not forgotten["runs"] and not forgotten["tests"]
                retained = await invoke("evident_inspect", {"run_id": baseline["run_id"]})
                assert retained["record"]["review"]["notes"][0]["title"] == note["title"]
                report = {"native_host": "PluginManager and registry.dispatch", "browser": "real managed Chromium",
                          "model": "not used; fixture-authored finding", "fresh_manager_recall": True,
                          "profile_isolation": True, "correction_and_forgetting": True, "outcomes": outcomes}
                (args.receipt_dir / "receipt.json").write_text(json.dumps(report, indent=2))
                print(json.dumps(report), flush=True)
            finally:
                manager.unload()
    finally:
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
