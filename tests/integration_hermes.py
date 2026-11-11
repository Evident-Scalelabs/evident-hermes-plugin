"""Real upstream loader/registry integration. Pass a clean upstream source checkout.

Run in an empty environment with HERMES_HOME pointing at a disposable profile.
This harness never requests a model or uses existing credentials.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--public", action="store_true", help="Also GET https://example.com/ (real external network)")
    parser.add_argument("--receipt-dir", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.upstream.resolve()))
    body = b"<h1>Synthetic office</h1>"

    async def handle(reader, writer):
        try:
            await reader.readuntil(b"\r\n\r\n")
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
            await writer.drain()
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    origin = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
    try:
        with tempfile.TemporaryDirectory(prefix="evidence-host-") as tmp:
            home = Path(tmp).resolve()
            os.environ["HERMES_HOME"] = str(home)
            os.environ["HERMES_BUNDLED_PLUGINS"] = str(home / "bundled")
            os.environ["HERMES_ENABLE_PROJECT_PLUGINS"] = "0"
            (home / "bundled").mkdir()
            candidate = Path(__file__).resolve().parents[1]
            destination = home / "plugins" / "evident-evidence"
            shutil.copytree(candidate, destination, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
            (home / "config.yaml").write_text(json.dumps({"plugins": {"enabled": ["evident-evidence"], "entries": {
                "evident-evidence": {"settings": {"fixture_origin": origin, "authorized_origins": ["https://example.com"] if args.public else []}}
            }}}))
            from hermes_cli.plugins import PluginManager
            from tools.registry import registry
            manager = PluginManager()
            manager.discover_and_load()

            async def invoke(name, arguments):
                result = await asyncio.to_thread(registry.dispatch, name, arguments, scope=manager.scope_key)
                return json.loads(result)

            try:
                plan = {"objective": "Check declared source text", "steps": [{"url": origin + "/", "assertions": [
                    {"kind": "text_contains", "expected": "Office hours"}]}], "limits": {"seconds": 10, "bytes_per_page": 65536}}
                baseline = await invoke("evident_observe", {"plan": plan})
                assert baseline.get("assertion_outcome") == "not_met", baseline
                args.receipt_dir.mkdir(parents=True, exist_ok=True)
                before = await invoke("evident_inspect", {"run_id": baseline["run_id"]})
                (args.receipt_dir / "synthetic-before.html").write_text(Path(before["report_path"]).read_text())
                (args.receipt_dir / "synthetic-before.json").write_text(json.dumps(before["record"], indent=2))
                changed_grader = await invoke("evident_verify", {"run_id": baseline["run_id"], "change_context": "injected criteria", "plan": plan})
                assert changed_grader["state"] == "unavailable", changed_grader
                body = b"<article><h2>Office hours</h2><p>Synthetic fixture</p></article>"
                repaired = await invoke("evident_verify", {"run_id": baseline["run_id"], "change_context": "Test harness changed synthetic source text"})
                assert repaired["verification"]["transitions"][0]["transition"] == "met_after", repaired
                inspected = await invoke("evident_inspect", {"run_id": repaired["run_id"]})
                assert "Office hours" in inspected["record"]["steps"][0]["source_text"]
                args.receipt_dir.mkdir(parents=True, exist_ok=True)
                (args.receipt_dir / "synthetic-after.html").write_text(Path(inspected["report_path"]).read_text())
                (args.receipt_dir / "synthetic-after.json").write_text(json.dumps(inspected["record"], indent=2))
                public = None
                if args.public:
                    plan["steps"][0] = {"url": "https://example.com/", "assertions": [{"kind": "text_contains", "expected": "Example Domain"}]}
                    public = await invoke("evident_observe", {"plan": plan})
                    assert public.get("assertion_outcome") == "met", public
                    evidence = await invoke("evident_inspect", {"run_id": public["run_id"]})
                    (args.receipt_dir / "public-example.json").write_text(json.dumps(evidence["record"], indent=2))
                other = home / "other-profile"
                other.mkdir()
                os.environ["HERMES_HOME"] = str(other)
                foreign = await invoke("evident_inspect", {"run_id": baseline["run_id"]})
                assert foreign["state"] == "unavailable", foreign
                os.environ["HERMES_HOME"] = str(home)
                result = {"host": "Unmodified upstream PluginManager + registry.dispatch, no mocks", "baseline": baseline,
                          "repaired": repaired, "public": public, "foreign_profile": foreign,
                          "host_approval": "Not exercised; source edit performed by authorized synthetic test harness"}
                (args.receipt_dir / "hermes-integration.json").write_text(json.dumps(result, indent=2))
                print(json.dumps({"real_host_loop": "passed", "public_https": "passed" if public else "not_run", "profile_isolation": "passed"}))
            finally:
                manager.unload()
    finally:
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
