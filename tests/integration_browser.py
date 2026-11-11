"""Real Hermes dispatch, Chromium, rendering and sockets. No mocked browser/model.

Run only where native isolated browser execution is authorized. Requires the
declared Playwright dependency and matching managed Chromium installed.
"""
import argparse
import asyncio
import base64
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
    parser.add_argument("--browser-server", default="", help="Explicit task-owned loopback Playwright worker; empty tests native launch")
    args = parser.parse_args()
    sys.path.insert(0, str(args.upstream.resolve()))
    requests = []
    hours = "Contact the team."
    index = b'''<!doctype html><html><head><link rel="stylesheet" href="/style.css"></head>
    <body><h1>Synthetic Studio</h1><p id="js">Source placeholder</p>
    <p hidden>Hidden source text</p><a id="hours" href="/hours">Hours</a>
    <button id="button">Unsafe action</button><a id="redirect" href="/redirect">External redirect</a>
    <a id="moved" href="/moved">Moved hours</a><a id="loop" href="/loop">Redirect loop</a>
    <script>document.querySelector('#js').textContent='Rendered by JavaScript';
    fetch('/forbidden-post',{method:'POST',body:'no'}).catch(()=>{});
    </script></body></html>'''

    async def handle(reader, writer):
        try:
            header = await reader.readuntil(b"\r\n\r\n")
            method, path, _ = header.split(b"\r\n", 1)[0].decode().split(" ")
            requests.append({"method": method, "path": path, "headers": header.decode()})
            mime = b"text/html"
            extra = b""
            status = b"200 OK"
            if path == "/":
                body = index
            elif path == "/hours":
                await asyncio.sleep(0.2)  # Redirect handoff must survive a delayed destination document.
                body = f"<html><body><h1>{hours}</h1></body></html>".encode()
            elif path == "/style.css":
                mime, body = b"text/css", b"body{font:24px system-ui;color:#123456}"
            elif path == "/redirect":
                status, extra, body = b"302 Found", b"Location: http://127.0.0.1:9/must-not-follow\r\n", b"redirect"
            elif path == "/moved":
                status, extra, body = b"301 Moved Permanently", b"Location: /hours\r\n", b"redirect"
            elif path == "/loop":
                status, extra, body = b"302 Found", b"Location: /loop\r\n", b"redirect"
            elif path == "/slow":
                await asyncio.sleep(3)
                body = b"Delayed synthetic response"
            else:
                body = b"Unexpected request"
            writer.write(b"HTTP/1.1 " + status + b"\r\nContent-Type: " + mime + b"\r\n" + extra +
                         b"Set-Cookie: synthetic=must-not-return\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
            await writer.drain()
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    origin = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
    try:
        with tempfile.TemporaryDirectory(prefix="evident-browser-host-") as tmp:
            home = Path(tmp).resolve()
            os.environ.update(HERMES_HOME=str(home), HERMES_BUNDLED_PLUGINS=str(home / "bundled"), HERMES_ENABLE_PROJECT_PLUGINS="0")
            (home / "bundled").mkdir()
            shutil.copytree(Path(__file__).resolve().parents[1], home / "plugins" / "evident-evidence",
                            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
            (home / "config.yaml").write_text(json.dumps({"plugins": {"enabled": ["evident-evidence"], "entries": {
                "evident-evidence": {"settings": {"fixture_origin": origin, "browser_enabled": True, "browser_server_url": args.browser_server, "authorized_origins": []}}}}}))
            from hermes_cli.plugins import PluginManager
            from tools.registry import registry
            manager = PluginManager()
            manager.discover_and_load()

            async def invoke(name, arguments):
                raw = await asyncio.to_thread(registry.dispatch, name, arguments, scope=manager.scope_key)
                return json.loads(raw) if isinstance(raw, str) else raw

            args.receipt_dir.mkdir(parents=True, exist_ok=True)
            try:
                plan = {"mode": "browser", "objective": "Read hours after following the declared link",
                        "viewport": {"width": 1280, "height": 800},
                        "limits": {"seconds": 30, "resources": 20, "bytes_per_resource": 65536},
                        "steps": [{"action": "open", "url": origin + "/", "assertions": [
                            {"kind": "visible_text", "expected": "Rendered by JavaScript"}]},
                            {"action": "follow_link", "selector": "#hours", "assertions": [
                                {"kind": "visible_text", "expected": "Weekday hours: 9 am to 5 pm"}]}]}
                before = await invoke("evident_browse", {"plan": plan})
                assert before.get("state") == "complete" and before["assertion_outcome"] == "not_met", before
                assert before["observed_steps"] == 2, before
                assert any(r["url"].endswith("/style.css") and r["state"] == "captured" for r in before["requests"]), before
                before_record = await invoke("evident_inspect", {"run_id": before["run_id"]})
                assert "Rendered by JavaScript" in before_record["record"]["steps"][0]["source_text"]
                assert "Hidden source text" not in before_record["record"]["steps"][0]["source_text"]
                shot = await invoke("evident_screenshot", {"run_id": before["run_id"], "step": 0})
                assert shot.get("_multimodal") is True, shot
                png = base64.b64decode(shot["content"][1]["image_url"]["url"].split(",", 1)[1])
                assert png.startswith(b"\x89PNG\r\n\x1a\n"), "Not a retained PNG"
                (args.receipt_dir / "rendered-home.png").write_bytes(png)
                step = before_record["record"]["steps"][0]
                element = next(i for i,e in enumerate(step["elements"]) if e["text"] == "Synthetic Studio")
                review = {"summary":"Synthetic evidence-linked review", "limitations":"Synthetic fixture; no customer research.",
                    "notes":[{"step":0,"title":"Studio heading is visible","observation":"The page names the studio.",
                        "quote":"Synthetic Studio","element":element,"implication":"Identity is stated; its effect on visitors is unmeasured.",
                        "suggested_change":"Retain the clear heading while testing the hours change.","uncertainty":"Synthetic content only."}]}
                report = await invoke("evident_report", {"run_id":before["run_id"],"review":review})
                assert report.get("state") == "saved", report
                html = Path(report["report_path"]).read_text()
                assert 'class="marker"' in html and 'data:image/png;base64,' in html and 'Synthetic evidence-linked review' in html
                (args.receipt_dir / "annotated-report.html").write_text(html)
                observation_plan = json.loads(json.dumps(plan))
                observation_plan["steps"] = [{**plan["steps"][0],"assertions":[]},{"action":"scroll","position":1,"assertions":[]}]
                observation = await invoke("evident_browse", {"plan":observation_plan})
                assert observation["state"] == "complete" and observation["assertion_outcome"] == "not_evaluated", observation
                hours = "Weekday hours: 9 am to 5 pm"
                after = await invoke("evident_verify", {"run_id": before["run_id"], "change_context": "Synthetic harness added hours"})
                assert after.get("state") == "complete", after
                after_view = await invoke("evident_inspect", {"run_id":after["run_id"]})
                assert 'Before &amp; after' in Path(after_view['report_path']).read_text()
                assert [t["transition"] for t in after["verification"]["transitions"]] == ["unchanged", "met_after"], after
                unchanged = await invoke("evident_verify", {"run_id": after["run_id"], "change_context": "No change"})
                assert all(t["transition"] == "unchanged" for t in unchanged["verification"]["transitions"]), unchanged
                hours = "Contact the team."
                regression = await invoke("evident_verify", {"run_id": after["run_id"], "change_context": "Synthetic harness removed hours"})
                assert regression["verification"]["transitions"][1]["transition"] == "regression", regression
                refused_plan = json.loads(json.dumps(plan))
                refused_plan["steps"][1]["selector"] = "#button"
                button = await invoke("evident_browse", {"plan": refused_plan})
                assert button.get("state") == "policy_stop" and button["observed_steps"] == 1, button
                refused_plan["steps"][1]["selector"] = "#redirect"
                redirect = await invoke("evident_browse", {"plan": refused_plan})
                assert redirect.get("state") != "complete" and redirect["observed_steps"] == 1, redirect
                assert any("Origin is not authorized" in r.get("reason", "") for r in redirect["requests"]), redirect
                refused_plan["steps"][1]["selector"] = "#moved"
                moved = await invoke("evident_browse", {"plan": refused_plan})
                assert moved['state']=='complete' and moved['observed_steps']==2, moved
                moved_record = await invoke("evident_inspect", {"run_id":moved['run_id']})
                assert moved_record['record']['steps'][1]['redirects']==[{'from':origin+'/moved','to':origin+'/hours','status':301}]
                refused_plan["steps"][1]["selector"] = "#loop"
                loop = await invoke("evident_browse", {"plan": refused_plan})
                assert loop['state']!='complete' and sum(r['path']=='/loop' for r in requests)==4, loop
                assert any('three-hop' in reason for reason in loop['limitations'])
                slow_plan = json.loads(json.dumps(plan))
                slow_plan["steps"] = [slow_plan["steps"][0]]
                slow_plan["steps"][0]["url"] = origin + "/slow"
                slow_plan["limits"]["seconds"] = 1
                timeout = await invoke("evident_browse", {"plan": slow_plan})
                assert timeout.get("state") == "timeout" and timeout["assertion_outcome"] == "unknown", timeout
                assert all(r["method"] == "GET" and r["path"] not in ("/forbidden-post", "/must-not-follow") for r in requests), requests
                assert all("\r\nCookie:" not in r["headers"] and "Authorization:" not in r["headers"] for r in requests), requests
                assert all('User-Agent: Evident-Evidence/0.1\r\n' in r['headers'] for r in requests), 'Every redirect hop must use the pinned transport, never a direct browser request'
                disabled_model = await invoke("evident_explain", {"run_id": before["run_id"], "consent": True})
                assert disabled_model.get("state") == "unavailable", disabled_model
                retained = args.receipt_dir / "runs"
                shutil.copytree(home / "plugin-data" / "evident-evidence", retained)
                receipt = {"test": "Real Hermes dispatch + fresh managed Chromium + synthetic HTTP server; no mocks",
                           "before": before, "after": after, "unchanged": unchanged, "regression": regression,
                           "button_refused": button, "redirect_refused": redirect, "same_origin_redirect":moved, "redirect_loop":loop, "server_requests": requests,
                           "timeout": timeout,
                           "model": "No model call; disabled configuration refusal exercised"}
                (args.receipt_dir / "browser-integration.json").write_text(json.dumps(receipt, indent=2))
                print(json.dumps({"rendered_host_integration": "passed", "browser": before["environment"]["browser"],
                                  "checks": ["annotated report", "observation-only scroll", "before/after HTML", "JavaScript rendering", "CSS", "hidden text exclusion", "anchor navigation", "PNG",
                                             "fixed assertions", "met_after", "unchanged", "regression", "button refusal",
                                             "cross-origin redirect refusal", "same-origin redirect", "redirect-loop bound", "bounded timeout", "POST prevention", "no credentials", "disabled model"]}))
            finally:
                manager.unload()
    finally:
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
